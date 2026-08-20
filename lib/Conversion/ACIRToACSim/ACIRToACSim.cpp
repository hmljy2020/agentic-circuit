// Atomic ACIR-to-ACSim whole-model lowering (ac-lower-to-acsim).
//
// Converts one frozen, verified ACIR file into one canonical acsim.model in a
// single transaction:
//   ac.module (concrete, () -> ())  -> acsim.module with ownership placements
//   ac.instance / ac.instances      -> acsim.instance (one per named member)
//   ac.array (homogeneous)          -> acsim.array
//   ac.module.extern                -> acsim.binding from the in-memory exact
//                                      binding resolution (no lock round-trip)
//   ac.process (yield-only plan)    -> acsim.process enum-PC state machine
//   selected ac.system              -> acsim.model with exact fingerprints,
//                                      canonical construction/destruction
//                                      order, dispatch rows, and self
//                                      activation edges
//
// Every validation failure is diagnosed with an ACLOWER-* code before any IR
// mutation, so a rejected input never publishes a partial acsim.model.
#include "acir/Conversion/ACIRToACSim/ACIRToACSim.h"

#include "acir/Analysis/ProcessStatePlan.h"
#include "acir/Bindings/Binding.h"
#include "acir/Dialect/ACIR/ACIROps.h"
#include "acir/Dialect/ACSim/ACSimDialect.h"
#include "acir/Dialect/ACSim/ACSimOps.h"
#include "acir/Dialect/ACSim/ACSimTypes.h"
#include "acir/Transforms/ResolveBindings.h"

#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/ControlFlow/IR/ControlFlowOps.h"
#include "mlir/Dialect/Index/IR/IndexDialect.h"
#include "mlir/Dialect/Index/IR/IndexOps.h"
#include "mlir/IR/Builders.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/Diagnostics.h"
#include "mlir/IR/Verifier.h"
#include "mlir/Pass/Pass.h"
#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/SmallSet.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/ADT/StringMap.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/ADT/StringSet.h"
#include "llvm/Support/Errc.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/raw_ostream.h"

#include <cctype>
#include <cmath>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

using namespace mlir;

namespace acir {
namespace {

constexpr llvm::StringLiteral kEpoch = "0.2";
constexpr llvm::StringLiteral kResultRoleIdentity = "acsim.result.role";
constexpr uint64_t kMaxExpandedRows = 1U << 20;

InFlightDiagnostic lowerError(Operation *op, llvm::StringRef code,
                              const llvm::Twine &message) {
  return op->emitError() << code << ": " << message;
}

// ---------------------------------------------------------------------------
// Canonical static values: MLIR attributes <-> RFC 8785 JSON
// ---------------------------------------------------------------------------

/// Convert a frozen ACIR static attribute to its canonical JSON value. The
/// accepted domain mirrors the ac-resolve-gfsim-bindings normalizer.
llvm::Expected<llvm::json::Value> staticValueToJson(Attribute attribute) {
  auto unsupported = [&]() {
    return llvm::createStringError(
        llvm::errc::invalid_argument,
        "ACLOWER-PARAM-PHASE: unsupported static attribute kind");
  };
  if (auto boolean = dyn_cast<BoolAttr>(attribute))
    return llvm::json::Value(boolean.getValue());
  if (auto integer = dyn_cast<IntegerAttr>(attribute)) {
    const llvm::APInt &value = integer.getValue();
    if (!value.isSignedIntN(64))
      return unsupported();
    return llvm::json::Value(value.getSExtValue());
  }
  if (auto floating = dyn_cast<FloatAttr>(attribute)) {
    double value = floating.getValueAsDouble();
    if (!std::isfinite(value) || (std::signbit(value) && value == 0.0))
      return unsupported();
    return llvm::json::Value(value);
  }
  if (auto string = dyn_cast<StringAttr>(attribute))
    return llvm::json::Value(string.getValue());
  if (auto array = dyn_cast<ArrayAttr>(attribute)) {
    llvm::json::Array values;
    for (Attribute element : array) {
      auto converted = staticValueToJson(element);
      if (!converted)
        return converted.takeError();
      values.push_back(std::move(*converted));
    }
    return llvm::json::Value(std::move(values));
  }
  if (auto dictionary = dyn_cast<DictionaryAttr>(attribute)) {
    llvm::json::Object values;
    for (NamedAttribute named : dictionary) {
      auto converted = staticValueToJson(named.getValue());
      if (!converted)
        return converted.takeError();
      values[named.getName().getValue()] = std::move(*converted);
    }
    return llvm::json::Value(std::move(values));
  }
  if (isa<TypeAttr, SymbolRefAttr>(attribute)) {
    std::string printed;
    llvm::raw_string_ostream output(printed);
    output << attribute;
    return llvm::json::Value(output.str());
  }
  return unsupported();
}

/// Convert a binding-lock JSON static value back to a canonical MLIR
/// attribute. Returns a null attribute for values outside the closed domain.
Attribute jsonToStaticAttribute(OpBuilder &builder,
                                const llvm::json::Value &value) {
  switch (value.kind()) {
  case llvm::json::Value::Boolean:
    return builder.getBoolAttr(*value.getAsBoolean());
  case llvm::json::Value::Number:
    if (auto integer = value.getAsInteger())
      return builder.getI64IntegerAttr(*integer);
    if (auto number = value.getAsNumber())
      return builder.getF64FloatAttr(*number);
    return Attribute();
  case llvm::json::Value::String:
    return builder.getStringAttr(*value.getAsString());
  case llvm::json::Value::Array: {
    llvm::SmallVector<Attribute> elements;
    for (const llvm::json::Value &element : *value.getAsArray()) {
      Attribute converted = jsonToStaticAttribute(builder, element);
      if (!converted)
        return Attribute();
      elements.push_back(converted);
    }
    return builder.getArrayAttr(elements);
  }
  case llvm::json::Value::Object: {
    llvm::SmallVector<NamedAttribute> members;
    for (const auto &member : *value.getAsObject()) {
      Attribute converted = jsonToStaticAttribute(builder, member.second);
      if (!converted)
        return Attribute();
      members.push_back(builder.getNamedAttr(member.first, converted));
    }
    return builder.getDictionaryAttr(members);
  }
  case llvm::json::Value::Null:
    return Attribute();
  }
  return Attribute();
}

/// Fingerprint a canonical JSON descriptor with the shared RFC 8785 + SHA-256
/// recipe used across the binding infrastructure.
std::string fingerprintJson(const llvm::json::Value &value) {
  auto canonical = bindings::canonicalizeJson(value);
  if (!canonical) {
    llvm::consumeError(canonical.takeError());
    return {};
  }
  return bindings::sha256Fingerprint(*canonical);
}

std::optional<std::string> nativeQueueCppType(Type payload, Operation *from) {
  if (auto integer = dyn_cast<IntegerType>(payload)) {
    if (!integer.isSignless())
      return std::nullopt;
    return llvm::StringSwitch<std::optional<std::string>>(
               std::to_string(integer.getWidth()))
        .Case("1", "bool")
        .Case("8", "std::int8_t")
        .Case("16", "std::int16_t")
        .Case("32", "std::int32_t")
        .Case("64", "std::int64_t")
        .Default(std::nullopt);
  }
  if (payload.isIndex())
    return std::string("std::size_t");
  if (payload.isF32())
    return std::string("float");
  if (payload.isF64())
    return std::string("double");
  if (auto packet = dyn_cast<ac::PacketType>(payload)) {
    Operation *packetDeclaration = nullptr;
    SymbolRefAttr name = packet.getName();
    if (name.getNestedReferences().size() == 1) {
      auto root = FlatSymbolRefAttr::get(name.getRootReference());
      Operation *scope = SymbolTable::lookupNearestSymbolFrom(from, root);
      if (!scope)
        if (auto module = from->getParentOfType<mlir::ModuleOp>())
          scope = SymbolTable::lookupSymbolIn(module, root);
      if (isa_and_nonnull<ac::TypeScopeOp>(scope))
        packetDeclaration =
            SymbolTable::lookupSymbolIn(scope, name.getLeafReference());
    } else {
      packetDeclaration = SymbolTable::lookupNearestSymbolFrom(from, name);
    }
    auto declaration = dyn_cast_or_null<ac::PacketOp>(packetDeclaration);
    if (!declaration)
      return std::nullopt;
    auto scope = dyn_cast<ac::TypeScopeOp>(declaration->getParentOp());
    if (!scope)
      return std::nullopt;
    DataLayoutSpecInterface spec = scope.getDataLayoutSpec();
    if (!spec)
      return std::nullopt;
    FailureOr<Attribute> value = spec.query(DataLayoutEntryKey(payload));
    if (failed(value))
      return std::nullopt;
    auto layout = dyn_cast<DictionaryAttr>(*value);
    auto width = layout ? layout.getAs<IntegerAttr>("serialization_width")
                        : IntegerAttr();
    if (!width || width.getInt() <= 0)
      return std::nullopt;
    return "std::array<std::byte, " + std::to_string(width.getInt()) + ">";
  }
  return std::nullopt;
}

// ---------------------------------------------------------------------------
// acsim.type symbol table
// ---------------------------------------------------------------------------

struct TypeDeclaration {
  std::string identity;
  std::string symbol;
  std::string cpp;
  std::string kind;
  std::string fingerprint;
  std::optional<uint64_t> period;
  uint64_t phase = 0;
  uint64_t tickScale = 1;
  std::optional<std::string> parent;
  std::optional<std::string> bridgeKind;
  std::optional<std::string> bridgeOwner;
};

/// Assigns deterministic canonical symbols and fingerprints to every C++
/// realization identity referenced by binding records or generated process
/// helpers. Identities are interned in sorted order so symbol assignment is
/// independent of discovery order.
class TypeSymbolTable {
public:
  /// Intern one identity. `fingerprint` may be empty, in which case the
  /// fingerprint is the SHA-256 of the identity itself.
  mlir::LogicalResult intern(Operation *reporter, llvm::StringRef identity,
                             llvm::StringRef kind, llvm::StringRef cpp,
                             llvm::StringRef fingerprint = llvm::StringRef()) {
    auto found = entries.find(identity.str());
    if (found != entries.end()) {
      TypeDeclaration &existing = found->second;
      if (existing.kind != kind || existing.cpp != cpp)
        return lowerError(reporter, "ACLOWER-TYPE-MISMATCH",
                          "realization identity '" + identity +
                              "' is used with conflicting acsim.type "
                              "kind or C++ spelling");
      if (!fingerprint.empty() && existing.fingerprint != fingerprint)
        return lowerError(
            reporter, "ACLOWER-FINGERPRINT",
            "realization identity '" + identity +
                "' carries conflicting fingerprints across binding records");
      return mlir::success();
    }
    TypeDeclaration declaration;
    declaration.identity = identity.str();
    declaration.kind = kind.str();
    declaration.cpp = cpp.str();
    declaration.fingerprint = fingerprint.empty()
                                  ? bindings::sha256Fingerprint(identity)
                                  : fingerprint.str();
    entries.emplace(declaration.identity, std::move(declaration));
    return mlir::success();
  }

  mlir::LogicalResult internTimeDomain(ac::TimeDomainOp domain) {
    llvm::json::Object descriptor{
        {"name", domain.getSymName()},
        {"period", static_cast<uint64_t>(domain.getPeriod())},
        {"phase", static_cast<uint64_t>(domain.getPhase())},
        {"tick_scale", static_cast<uint64_t>(domain.getTickScale())}};
    if (auto parent = domain.getParentAttr())
      descriptor["parent"] = parent.getValue();
    else
      descriptor["parent"] = nullptr;
    if (auto bridge = domain.getBridgeAttr()) {
      descriptor["bridge"] = llvm::json::Object{
          {"kind", bridge.getAs<StringAttr>("kind").getValue()},
          {"owner", bridge.getAs<FlatSymbolRefAttr>("owner").getValue()}};
    } else {
      descriptor["bridge"] = nullptr;
    }
    std::string fingerprint =
        fingerprintJson(llvm::json::Value(std::move(descriptor)));
    if (failed(intern(domain, domain.getSymName(), "time_domain",
                      "gfsim::TimeDomainRuntime", fingerprint)))
      return mlir::failure();
    TypeDeclaration &declaration = entries.at(domain.getSymName().str());
    declaration.period = static_cast<uint64_t>(domain.getPeriod());
    declaration.phase = static_cast<uint64_t>(domain.getPhase());
    declaration.tickScale = static_cast<uint64_t>(domain.getTickScale());
    if (auto parent = domain.getParentAttr())
      declaration.parent = parent.getValue().str();
    if (auto bridge = domain.getBridgeAttr()) {
      declaration.bridgeKind =
          bridge.getAs<StringAttr>("kind").getValue().str();
      declaration.bridgeOwner =
          bridge.getAs<FlatSymbolRefAttr>("owner").getValue().str();
    }
    return mlir::success();
  }

  /// Resolve symbols after all identities are interned.
  mlir::LogicalResult finalize(Operation *reporter) {
    llvm::StringMap<std::string> ownerBySymbol;
    for (auto &[identity, declaration] : entries) {
      std::string base = sanitize(declaration.identity);
      std::string symbol = base;
      for (unsigned suffix = 2; ownerBySymbol.count(symbol); ++suffix)
        symbol = base + "_" + std::to_string(suffix);
      ownerBySymbol.try_emplace(symbol, declaration.identity);
      declaration.symbol = symbol;
    }
    ordered.clear();
    for (auto &[identity, declaration] : entries)
      ordered.push_back(&declaration);
    llvm::sort(ordered,
               [](const TypeDeclaration *left, const TypeDeclaration *right) {
                 return left->symbol < right->symbol;
               });
    for (const TypeDeclaration *declaration : ordered)
      if (declaration->symbol.empty())
        return lowerError(reporter, "ACLOWER-FINGERPRINT",
                          "realization identity '" + declaration->identity +
                              "' has no canonical symbol");
    return mlir::success();
  }

  llvm::StringRef symbolFor(llvm::StringRef identity) const {
    auto found = entries.find(identity.str());
    return found == entries.end() ? llvm::StringRef()
                                  : llvm::StringRef(found->second.symbol);
  }

  llvm::ArrayRef<const TypeDeclaration *> declarations() const {
    return ordered;
  }

private:
  static std::string sanitize(llvm::StringRef identity) {
    std::string symbol;
    symbol.reserve(identity.size());
    for (char character : identity)
      symbol.push_back(std::isalnum(static_cast<unsigned char>(character)) ||
                               character == '_'
                           ? character
                           : '_');
    if (symbol.empty() ||
        std::isdigit(static_cast<unsigned char>(symbol.front())))
      symbol.insert(symbol.begin(), '_');
    return symbol;
  }

  std::map<std::string, TypeDeclaration> entries;
  llvm::SmallVector<const TypeDeclaration *> ordered;
};

// ---------------------------------------------------------------------------
// Binding record conversion
// ---------------------------------------------------------------------------

/// Build the exact 20-field acsim.binding record dictionary from a typed
/// binding-lock record, mapping realization identities to canonical symbols.
mlir::Attribute convertBindingRecord(OpBuilder &builder,
                                     const bindings::BindingRecord &record,
                                     const TypeSymbolTable &types) {
  MLIRContext *context = builder.getContext();
  auto string = [&](llvm::StringRef value) {
    return builder.getStringAttr(value);
  };
  auto reference = [&](llvm::StringRef identity) {
    return FlatSymbolRefAttr::get(context, types.symbolFor(identity));
  };
  auto dictionary =
      [&](llvm::ArrayRef<NamedAttribute> members) -> DictionaryAttr {
    return builder.getDictionaryAttr(members);
  };
  auto named = [&](llvm::StringRef key, Attribute value) {
    return builder.getNamedAttr(key, value);
  };

  llvm::SmallVector<Attribute> activationSources;
  for (const bindings::ActivationSourceBinding &source :
       record.activationSources())
    activationSources.push_back(
        dictionary({named("kind", reference(source.kind)),
                    named("name", string(source.name))}));

  llvm::SmallVector<Attribute> constructionArguments;
  for (const llvm::json::Value &argument : record.construction().arguments)
    constructionArguments.push_back(jsonToStaticAttribute(builder, argument));

  const bindings::CppBinding &cpp = record.cpp();
  DictionaryAttr entryPoints =
      dictionary({named("pure", string(cpp.entryPoints.pure)),
                  named("reset", string(cpp.entryPoints.reset)),
                  named("validate", string(cpp.entryPoints.validate)),
                  named("work", string(cpp.entryPoints.work)),
                  named("xfer", string(cpp.entryPoints.xfer))});
  DictionaryAttr cppRecord = dictionary(
      {named("concept", string(cpp.conceptName)),
       named("entry_points", entryPoints), named("header", string(cpp.header)),
       named("symbol", string(cpp.symbol)),
       named("target", string(cpp.target))});

  DictionaryAttr construction = dictionary(
      {named("arguments", builder.getArrayAttr(constructionArguments)),
       named("kind", string(record.construction().kind))});
  DictionaryAttr ownership =
      dictionary({named("kind", string(record.ownership().kind)),
                  named("placement", string(record.ownership().placement))});

  llvm::SmallVector<Attribute> parameters;
  for (const bindings::ParameterBinding &parameter : record.parameters())
    parameters.push_back(dictionary(
        {named("acir_type", string(parameter.acirType)),
         named("cpp_type", string(parameter.cppType)),
         named("mapping", string(parameter.mapping)),
         named("name", string(parameter.name)),
         named("ordinal", builder.getI64IntegerAttr(parameter.ordinal)),
         named("value", jsonToStaticAttribute(builder, parameter.value))}));

  llvm::SmallVector<Attribute> ports;
  for (const bindings::PortBinding &port : record.ports())
    ports.push_back(
        dictionary({named("accessor", reference(port.accessor)),
                    named("cardinality", string(port.cardinality)),
                    named("delegation", string(port.delegation)),
                    named("direction", string(port.direction)),
                    named("interface", reference(port.interface)),
                    named("ownership", string(port.ownership)),
                    named("payload", reference(port.payload)),
                    named("protocol", reference(port.protocol)),
                    named("role", reference(port.role)),
                    named("time_domain", reference(port.timeDomain))}));

  llvm::SmallVector<Attribute> resources;
  for (const bindings::ResourceBinding &resource : record.resources())
    resources.push_back(
        dictionary({named("accessor", reference(resource.accessor)),
                    named("delegation", string(resource.delegation)),
                    named("mode", string(resource.mode)),
                    named("ownership", string(resource.ownership)),
                    named("resource", reference(resource.resource)),
                    named("role", reference(resource.role)),
                    named("time_domain", reference(resource.timeDomain))}));

  llvm::SmallVector<Attribute> results;
  for (const bindings::ResultBinding &result : record.results())
    results.push_back(dictionary({named("cpp_type", reference(result.cppType)),
                                  named("name", string(result.name))}));

  return dictionary(
      {named("activation_sources", builder.getArrayAttr(activationSources)),
       named("availability", string(record.availability())),
       named("binding", string(record.binding())),
       named("binding_schema", string(record.bindingSchema())),
       named("component_schema", reference(record.componentSchema())),
       named("component_schema_fingerprint",
             string(record.componentSchemaFingerprint())),
       named("construction", construction),
       named("contract_epoch", string(record.contractEpoch())),
       named("cpp", cppRecord),
       named("cpp_type", reference(record.cppType())),
       named("effect", string(record.effect())),
       named("fingerprint", string(record.fingerprint())),
       named("implementation", reference(record.implementation())),
       named("ownership", ownership),
       named("parameters", builder.getArrayAttr(parameters)),
       named("ports", builder.getArrayAttr(ports)),
       named("provider", reference(record.provider())),
       named("provider_implementation_fingerprint",
             string(record.providerImplementationFingerprint())),
       named("resources", builder.getArrayAttr(resources)),
       named("results", builder.getArrayAttr(results))});
}

// ---------------------------------------------------------------------------
// Module and placement plans
// ---------------------------------------------------------------------------

struct PortEndpointPlan {
  Value value;
  bindings::PortBinding metadata;
  bool nativeFlow = false;
};

struct PlacementPlan {
  enum class Kind { Instance, Array, RuntimeObject, Process };
  Kind kind = Kind::Instance;
  std::string name;
  // Instance/array realization.
  std::string targetSymbol;
  bool targetIsBinding = false;
  bool targetIsRuntimeObject = false;
  bool targetIsPure = false;
  std::string resultCppType;
  ArrayAttr staticArgs;
  std::string specialization;
  llvm::SmallVector<int64_t, 2> shape;
  // Binding-target dispatch thunks.
  std::string work;
  std::string xfer;
  std::string reset;
  std::string validate;
  llvm::SmallVector<PortEndpointPlan, 2> inputPorts;
  llvm::SmallVector<PortEndpointPlan, 2> outputPorts;
  llvm::SmallVector<std::pair<Value, Value>, 2> flowAliases;
  // Process realization.
  ac::ProcessOp process;
  std::string processDefinitionKey;
  uint64_t fairnessCap = 1;
  ac::QueueOp queue;
  ac::EventQueueOp eventQueue;
  bool flowLink = false;
};

struct BindingEdgePlan {
  unsigned sourcePlacement = 0;
  unsigned targetPlacement = 0;
  bool activates = true;
  bool nativeFlow = false;
  std::string sourceChild;
  std::string targetChild;
  unsigned linkPlacement = 0;
};

struct PureCallPlan {
  ac::InstanceOp source;
  Value result;
  std::string name;
  std::string binding;
  std::string cppType;
};

struct ModuleResultPlan {
  Value source;
  std::string name;
  std::string cppType;
};

struct ModulePortPlan {
  Value source;
  std::string name;
  bindings::PortBinding metadata;
  std::string queue;
  std::string localAccessor;
  bool nativeFlow = false;
  int64_t inputIndex = -1;
  int64_t resultIndex = -1;
};

struct ModulePlan {
  ac::ModuleOp source;
  std::string name;
  ArrayAttr staticParams;
  std::string specialization;
  llvm::SmallVector<PlacementPlan, 0> placements;
  llvm::SmallVector<PureCallPlan, 0> pureCalls;
  llvm::SmallVector<ModulePortPlan, 0> ports;
  llvm::SmallVector<ModuleResultPlan, 0> results;
  llvm::SmallVector<std::pair<unsigned, unsigned>, 0> flowAliases;
  llvm::SmallVector<BindingEdgePlan, 0> bindingEdges;
};

// ---------------------------------------------------------------------------
// The pass
// ---------------------------------------------------------------------------

class ACIRToACSimPass final
    : public PassWrapper<ACIRToACSimPass, OperationPass<mlir::ModuleOp>> {
public:
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(ACIRToACSimPass)

  explicit ACIRToACSimPass(ACIRToACSimPassOptions options)
      : options(std::move(options)) {}

  llvm::StringRef getArgument() const override { return "ac-lower-to-acsim"; }
  llvm::StringRef getDescription() const override {
    return "Atomically lower one frozen ACIR model to canonical ACSim";
  }

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<acsim::ACSimDialect, mlir::arith::ArithDialect,
                    mlir::index::IndexDialect, mlir::cf::ControlFlowDialect>();
  }

  void runOnOperation() override {
    if (failed(lower(getOperation())))
      signalPassFailure();
  }

private:
  mlir::LogicalResult lower(mlir::ModuleOp input);
  mlir::LogicalResult lowerArbiters(mlir::ModuleOp input);

  /// Validation and planning. No IR mutation happens in this phase.
  mlir::LogicalResult plan(mlir::ModuleOp input);

  mlir::LogicalResult planModule(ac::ModuleOp module, ModulePlan &planned);
  mlir::LogicalResult planInstanceTarget(Operation *placement,
                                         llvm::StringRef definition,
                                         DictionaryAttr staticArgs,
                                         PlacementPlan &planned);
  mlir::LogicalResult planInstancePorts(ac::InstanceOp instance,
                                        PlacementPlan &planned);
  mlir::FailureOr<bindings::PortBinding>
  nativeFlowPort(Operation *reporter, ac::FlowType flow,
                 llvm::StringRef direction, llvm::StringRef accessorIdentity,
                 llvm::StringRef accessorCpp);
  mlir::LogicalResult planProcesses(mlir::ModuleOp input);
  mlir::LogicalResult expand(mlir::ModuleOp input);

  void expandModule(unsigned moduleIndex, std::string pathPrefix,
                    llvm::SmallSet<unsigned, 8> &active);

  /// Emission. Runs only after every check succeeded.
  mlir::FailureOr<mlir::OwningOpRef<mlir::ModuleOp>> emit(mlir::ModuleOp input);
  void publish(mlir::ModuleOp input, mlir::ModuleOp staged);
  void emitModuleBody(OpBuilder &builder, const ModulePlan &planned);
  void emitProcessBody(OpBuilder &builder, const PlacementPlan &placement,
                       const llvm::DenseMap<Value, Value> &moduleValues,
                       const llvm::StringMap<Value> &queueOwners);

  std::string moduleFingerprint(ac::ModuleOp module);
  std::string processFingerprint(const ModulePlan &module,
                                 const PlacementPlan &process);
  std::string bindingInstanceFingerprint(const bindings::BindingRecord &record,
                                         ArrayAttr values);

  ACIRToACSimPassOptions options;

  // Planning state.
  ac::SystemOp selectedSystem;
  llvm::StringMap<unsigned> moduleIndexByName; // concrete modules
  llvm::StringMap<ac::ModuleExternOp> externByName;
  llvm::SmallVector<ModulePlan, 0> modules; // sorted by name
  llvm::SmallVector<ac::TimeDomainOp, 0> timeDomains;
  std::optional<bindings::BindingResolutionResult> resolution;
  std::optional<ProcessStatePlanSet> processPlans;
  std::string processPlanBytes;
  TypeSymbolTable typeSymbols;
  std::vector<std::string> generatedCalleeIdentities;
  std::vector<std::string> valueTypeIdentities;
  llvm::DenseMap<mlir::Type, std::string> nativePacketValueIdentities;
  llvm::StringMap<std::string> wakeTypeIdentities;

  struct RuntimeRow {
    unsigned moduleIndex;
    unsigned placementIndex;
    std::string contextPath;
    std::string path;
    llvm::SmallVector<int64_t, 2> indices;
  };
  llvm::SmallVector<std::string> constructionOrder;
  llvm::SmallVector<RuntimeRow> runtimeRows;
  llvm::StringSet<> frozenOwnerPaths;

  // Fingerprints.
  std::string frozenAcirFingerprint;
  std::string bindingLockFingerprint;
  std::string providerFingerprint;
  std::string schemaSetFingerprint;
  std::string profileFingerprint;
  std::string toolchainFingerprint;

  // Set when owner expansion detects an instantiation cycle.
  bool expansionCycle = false;
};

mlir::FailureOr<bindings::PortBinding> ACIRToACSimPass::nativeFlowPort(
    Operation *reporter, ac::FlowType flow, llvm::StringRef direction,
    llvm::StringRef accessorIdentity, llvm::StringRef accessorCpp) {
  auto payloadCpp = nativeQueueCppType(flow.getElementType(), reporter);
  if (!payloadCpp) {
    lowerError(reporter, "ACLOWER-TYPE-MISMATCH",
               "native Flow payload has no closed C++ realization");
    return failure();
  }
  std::string payloadSpelling;
  llvm::raw_string_ostream(payloadSpelling) << flow.getElementType();
  std::string payloadIdentity =
      "acir_flow_payload_" +
      llvm::StringRef(bindings::sha256Fingerprint(payloadSpelling))
          .drop_front(7)
          .str();
  std::string protocolIdentity =
      "acir_flow_protocol_" + flow.getProtocol().getValue().str();
  constexpr llvm::StringLiteral interfaceIdentity =
      "acir_native_flow_interface";
  constexpr llvm::StringLiteral sourceRole = "acir_native_flow_source";
  constexpr llvm::StringLiteral sinkRole = "acir_native_flow_sink";
  constexpr llvm::StringLiteral timeDomain = "acir_native_flow_time";
  if (failed(typeSymbols.intern(reporter, interfaceIdentity, "interface",
                                "acir::native_flow_interface")) ||
      failed(typeSymbols.intern(reporter, sourceRole, "role",
                                "acir::native_flow_source")) ||
      failed(typeSymbols.intern(reporter, sinkRole, "role",
                                "acir::native_flow_sink")) ||
      failed(typeSymbols.intern(reporter, timeDomain, "time_domain",
                                "gfsim::TimeDomainRuntime")) ||
      failed(typeSymbols.intern(
          reporter, payloadIdentity,
          isa<ac::PacketType>(flow.getElementType()) ? "packet" : "value",
          *payloadCpp)) ||
      failed(typeSymbols.intern(reporter, protocolIdentity, "protocol",
                                "acir::native_flow_protocol")) ||
      failed(typeSymbols.intern(reporter, accessorIdentity, "accessor",
                                accessorCpp)))
    return failure();
  bindings::PortBinding port;
  port.accessor = accessorIdentity.str();
  port.cardinality = "exclusive";
  port.delegation = "forbidden";
  port.direction = direction.str();
  port.interface = interfaceIdentity.str();
  port.ownership = "owned";
  port.payload = std::move(payloadIdentity);
  port.protocol = std::move(protocolIdentity);
  port.role = (direction == "output" ? sourceRole : sinkRole).str();
  port.timeDomain = timeDomain.str();
  return port;
}

std::string ACIRToACSimPass::moduleFingerprint(ac::ModuleOp module) {
  llvm::json::Object descriptor;
  descriptor["module"] = module.getSymName();
  auto typeSpelling = [](Type type) {
    std::string storage;
    llvm::raw_string_ostream stream(storage);
    stream << type;
    return storage;
  };
  auto staticDictionary = [&](DictionaryAttr dictionary) {
    llvm::json::Object values;
    if (!dictionary)
      return values;
    for (NamedAttribute named : dictionary) {
      auto value = staticValueToJson(named.getValue());
      if (!value) {
        llvm::consumeError(value.takeError());
        continue;
      }
      values[named.getName().getValue()] = std::move(*value);
    }
    return values;
  };
  auto targetFingerprint = [&](llvm::StringRef target) {
    if (auto concrete = moduleIndexByName.find(target);
        concrete != moduleIndexByName.end())
      return modules[concrete->second].specialization;
    if (resolution) {
      std::string key = ("@" + target).str();
      if (const bindings::ResolvedBinding *selection =
              resolution->selectionForResolutionKey(key))
        return selection->record().fingerprint().str();
    }
    return std::string();
  };

  llvm::json::Object interface;
  llvm::json::Array inputs;
  llvm::json::Array results;
  for (Type type : module.getFunctionType().getInputs())
    inputs.push_back(typeSpelling(type));
  for (Type type : module.getFunctionType().getResults())
    results.push_back(typeSpelling(type));
  interface["inputs"] = std::move(inputs);
  interface["results"] = std::move(results);
  descriptor["interface"] = std::move(interface);

  llvm::json::Object parameters;
  for (NamedAttribute named : module.getStaticParams()) {
    auto value = staticValueToJson(named.getValue());
    if (!value) {
      llvm::consumeError(value.takeError());
      continue;
    }
    parameters[named.getName().getValue()] = std::move(*value);
  }
  descriptor["static"] = std::move(parameters);

  std::vector<std::pair<std::string, llvm::json::Object>> definitions;
  auto appendPlacement = [&](llvm::StringRef key, llvm::StringRef kind,
                             llvm::StringRef name, llvm::StringRef target,
                             DictionaryAttr staticArgs) {
    llvm::json::Object entry;
    entry["kind"] = kind;
    entry["name"] = name;
    entry["static"] = staticDictionary(staticArgs);
    entry["target"] = target;
    entry["target_specialization"] = targetFingerprint(target);
    definitions.emplace_back(key.str(), std::move(entry));
  };
  for (Operation &operation : module.getBody().front()) {
    if (auto instance = dyn_cast<ac::InstanceOp>(operation)) {
      appendPlacement(("instance:" + instance.getSymName()).str(), "instance",
                      instance.getSymName(), instance.getDefinition(),
                      instance.getStaticArgs());
      continue;
    }
    if (auto array = dyn_cast<ac::ArrayOp>(operation)) {
      llvm::json::Object entry;
      entry["kind"] = "array";
      entry["name"] = array.getSymName();
      entry["target"] = array.getDefinition();
      entry["target_specialization"] = targetFingerprint(array.getDefinition());
      llvm::json::Array shape;
      for (int64_t extent : array.getShape())
        shape.push_back(extent);
      entry["shape"] = std::move(shape);
      llvm::json::Array staticElements;
      for (Attribute arguments : array.getStaticArgs())
        staticElements.push_back(
            staticDictionary(cast<DictionaryAttr>(arguments)));
      entry["static"] = std::move(staticElements);
      definitions.emplace_back(("array:" + array.getSymName()).str(),
                               std::move(entry));
      continue;
    }
    if (auto collection = dyn_cast<ac::InstancesOp>(operation)) {
      for (auto [index, nameAttribute] :
           llvm::enumerate(collection.getNames())) {
        llvm::StringRef name = cast<StringAttr>(nameAttribute).getValue();
        llvm::StringRef target =
            cast<FlatSymbolRefAttr>(collection.getDefinitions()[index])
                .getValue();
        appendPlacement(
            ("instance:" + name).str(), "instance", name, target,
            cast<DictionaryAttr>(collection.getStaticArgs()[index]));
      }
      continue;
    }
    if (auto process = dyn_cast<ac::ProcessOp>(operation)) {
      llvm::json::Object entry;
      entry["kind"] = "process";
      entry["name"] = process.getSymName();
      entry["process_kind"] = process.getKind();
      llvm::json::Array captureTypes;
      for (Value capture : process.getCaptures())
        captureTypes.push_back(typeSpelling(capture.getType()));
      entry["captures"] = std::move(captureTypes);
      llvm::json::Array skeleton;
      if (auto frozenSkeleton =
              process->getAttrOfType<ArrayAttr>("ac.frozen_process_skeleton"))
        for (Attribute line : frozenSkeleton)
          skeleton.push_back(cast<StringAttr>(line).getValue());
      entry["skeleton"] = std::move(skeleton);
      definitions.emplace_back(("process:" + process.getSymName()).str(),
                               std::move(entry));
      continue;
    }
    if (auto queue = dyn_cast<ac::QueueOp>(operation)) {
      llvm::json::Object entry;
      entry["kind"] = "runtime_queue";
      entry["name"] = queue.getSymName();
      entry["stable_id"] = queue.getStableId();
      entry["path"] = queue.getPath();
      entry["payload"] = typeSpelling(queue.getPayload());
      entry["entry_capacity"] = queue.getEntryCapacity();
      if (queue.getByteCapacityAttr())
        entry["byte_capacity"] = queue.getByteCapacity();
      entry["ordering"] = queue.getOrdering();
      entry["ownership"] = queue.getOwnership();
      entry["delay_ticks"] = queue.getDelayTicks();
      definitions.emplace_back(("queue:" + queue.getSymName()).str(),
                               std::move(entry));
      continue;
    }
    if (auto domain = dyn_cast<ac::TimeDomainOp>(operation)) {
      llvm::json::Object entry{
          {"kind", "time_domain"},
          {"name", domain.getSymName()},
          {"period", static_cast<uint64_t>(domain.getPeriod())},
          {"phase", static_cast<uint64_t>(domain.getPhase())},
          {"tick_scale", static_cast<uint64_t>(domain.getTickScale())}};
      if (auto parent = domain.getParentAttr())
        entry["parent"] = parent.getValue();
      if (auto bridge = domain.getBridgeAttr())
        entry["bridge"] = llvm::json::Object{
            {"kind", bridge.getAs<StringAttr>("kind").getValue()},
            {"owner", bridge.getAs<FlatSymbolRefAttr>("owner").getValue()}};
      definitions.emplace_back(("time_domain:" + domain.getSymName()).str(),
                               std::move(entry));
      continue;
    }
    if (auto returnOp = dyn_cast<ac::ReturnOp>(operation)) {
      llvm::json::Object entry;
      entry["kind"] = "return";
      llvm::json::Array operandTypes;
      for (Value operand : returnOp.getOperands())
        operandTypes.push_back(typeSpelling(operand.getType()));
      entry["operands"] = std::move(operandTypes);
      definitions.emplace_back("~return", std::move(entry));
    }
  }
  llvm::sort(definitions, [](const auto &left, const auto &right) {
    return left.first < right.first;
  });
  llvm::json::Array body;
  for (auto &definition : definitions)
    body.push_back(std::move(definition.second));
  descriptor["body"] = std::move(body);
  return fingerprintJson(llvm::json::Value(std::move(descriptor)));
}

std::string ACIRToACSimPass::processFingerprint(const ModulePlan &module,
                                                const PlacementPlan &process) {
  llvm::json::Object descriptor;
  descriptor["module"] = module.name;
  descriptor["module_specialization"] = module.specialization;
  descriptor["process"] = process.name;
  descriptor["process_plan"] = bindings::sha256Fingerprint(processPlanBytes);
  return fingerprintJson(llvm::json::Value(std::move(descriptor)));
}

std::string ACIRToACSimPass::bindingInstanceFingerprint(
    const bindings::BindingRecord &record, ArrayAttr values) {
  llvm::json::Object descriptor;
  descriptor["binding"] = record.binding();
  descriptor["binding_fingerprint"] = record.fingerprint();
  descriptor["component_schema_fingerprint"] =
      record.componentSchemaFingerprint();
  descriptor["profile"] = options.profile;
  descriptor["provider_implementation_fingerprint"] =
      record.providerImplementationFingerprint();
  llvm::json::Array staticValues;
  for (Attribute value : values) {
    auto converted = staticValueToJson(value);
    if (!converted) {
      llvm::consumeError(converted.takeError());
      continue;
    }
    staticValues.push_back(std::move(*converted));
  }
  descriptor["static"] = std::move(staticValues);
  descriptor["target"] = options.target;
  return fingerprintJson(llvm::json::Value(std::move(descriptor)));
}

// ---------------------------------------------------------------------------
// Planning
// ---------------------------------------------------------------------------

mlir::LogicalResult ACIRToACSimPass::planInstanceTarget(
    Operation *placement, llvm::StringRef definition, DictionaryAttr staticArgs,
    PlacementPlan &planned) {
  auto externIt = externByName.find(definition);
  auto moduleIt = moduleIndexByName.find(definition);
  if (externIt == externByName.end() && moduleIt == moduleIndexByName.end())
    return lowerError(placement, "ACLOWER-BINDING-MISSING",
                      "placement definition '@" + definition +
                          "' is not a module or external declaration");

  DictionaryAttr declaredParams;
  if (externIt != externByName.end())
    declaredParams = externIt->second.getStaticParams();
  else
    declaredParams = modules[moduleIt->second].source.getStaticParams();
  // Zero-volume arrays carry no per-element dictionaries; the declared
  // parameters are the single specialization.
  if (staticArgs && staticArgs != declaredParams)
    return lowerError(placement, "ACLOWER-PARAM-PHASE",
                      "placement static arguments must exactly equal the "
                      "frozen static parameters of '@" +
                          definition +
                          "' (per-instance specialization is outside the v0.2 "
                          "lowering stage)");

  if (externIt != externByName.end()) {
    // External declaration: realization comes from the exact binding lock.
    std::string key = ("@" + definition).str();
    const bindings::ResolvedBinding *selection =
        resolution->selectionForResolutionKey(key);
    if (!selection)
      return lowerError(placement, "ACLOWER-BINDING-MISSING",
                        "no exact binding selection exists for external "
                        "declaration '@" +
                            definition + "'");
    const bindings::BindingRecord &record = selection->record();
    if (record.effect() != "stateful" && record.effect() != "pure")
      return lowerError(placement, "ACLOWER-TYPE-MISMATCH",
                        "external declaration '@" + definition +
                            "' resolved to binding '" + record.binding() +
                            "' with unknown effect '" + record.effect() + "'");
    // Registry validation has already proven the effect-specific entry-point
    // set and exact result metadata.
    const bindings::CppEntryPoints &entryPoints = record.cpp().entryPoints;
    planned.targetSymbol = record.binding().str();
    planned.targetIsBinding = true;
    planned.targetIsPure = record.effect() == "pure";
    if (planned.targetIsPure) {
      if (record.results().size() != 1)
        return lowerError(
            placement, "ACLOWER-TYPE-MISMATCH",
            "pure binding '" + record.binding() +
                "' must have exactly one result for acsim.inline");
      planned.resultCppType = record.results().front().cppType;
    }
    OpBuilder builder(placement->getContext());
    llvm::SmallVector<Attribute> values;
    for (const bindings::ParameterBinding &parameter : record.parameters()) {
      Attribute value = jsonToStaticAttribute(builder, parameter.value);
      if (!value)
        return lowerError(placement, "ACLOWER-PARAM-PHASE",
                          "binding '" + record.binding() + "' parameter '" +
                              parameter.name +
                              "' has a value outside the canonical static "
                              "domain");
      values.push_back(value);
    }
    planned.staticArgs = builder.getArrayAttr(values);
    planned.specialization =
        bindingInstanceFingerprint(record, planned.staticArgs);
    if (!planned.targetIsPure) {
      planned.work = entryPoints.work;
      planned.xfer = entryPoints.xfer;
      planned.reset = entryPoints.reset;
      planned.validate = entryPoints.validate;
    }
    return mlir::success();
  }

  // Concrete generated module target.
  ModulePlan &target = modules[moduleIt->second];
  planned.targetSymbol = target.name;
  planned.targetIsBinding = false;
  planned.staticArgs = target.staticParams;
  planned.specialization = target.specialization;
  return mlir::success();
}

mlir::LogicalResult ACIRToACSimPass::planInstancePorts(ac::InstanceOp instance,
                                                       PlacementPlan &planned) {
  if (!planned.targetIsBinding) {
    auto target = moduleIndexByName.find(instance.getDefinition());
    if (target == moduleIndexByName.end())
      return mlir::success();
    const ModulePlan &module = modules[target->second];
    for (const ModulePortPlan &port : module.ports) {
      if (!port.nativeFlow)
        continue;
      if (port.inputIndex >= 0) {
        if (static_cast<unsigned>(port.inputIndex) >= instance.getNumOperands())
          return lowerError(
              instance, "ACLOWER-TYPE-MISMATCH",
              "native Flow input index is outside instance interface");
        planned.inputPorts.push_back(
            {instance.getOperand(port.inputIndex), port.metadata, true});
      } else if (port.resultIndex >= 0) {
        if (static_cast<unsigned>(port.resultIndex) >= instance.getNumResults())
          return lowerError(
              instance, "ACLOWER-TYPE-MISMATCH",
              "native Flow result index is outside instance interface");
        planned.outputPorts.push_back(
            {instance.getResult(port.resultIndex), port.metadata, true});
      }
    }
    for (auto [resultIndex, inputIndex] : module.flowAliases) {
      if (resultIndex >= instance.getNumResults() ||
          inputIndex >= instance.getNumOperands())
        return lowerError(
            instance, "ACLOWER-TYPE-MISMATCH",
            "native Flow pass-through index is outside instance interface");
      planned.flowAliases.push_back(
          {instance.getResult(resultIndex), instance.getOperand(inputIndex)});
    }
    return mlir::success();
  }
  if (planned.targetIsPure)
    return mlir::success();
  std::string key = ("@" + instance.getDefinition()).str();
  const bindings::ResolvedBinding *selection =
      resolution->selectionForResolutionKey(key);
  assert(selection && "validated external target must have a binding");
  const bindings::BindingRecord &record = selection->record();
  llvm::SmallVector<bool> used(record.ports().size(), false);

  auto planEndpoint = [&](Value value, llvm::StringRef direction,
                          llvm::SmallVectorImpl<PortEndpointPlan> &endpoints)
      -> mlir::LogicalResult {
    auto endpoint = dyn_cast<ac::EndpointType>(value.getType());
    if (!endpoint) {
      if (direction == "input" || !value.use_empty())
        return lowerError(instance, "ACLOWER-TYPE-MISMATCH",
                          "stateful binding scalar values cannot cross the "
                          "construction graph; use a typed endpoint/resource "
                          "or a pure binding result");
      return mlir::success();
    }
    llvm::StringRef expectedRole = endpoint.getRole().getValue();
    if (direction == "input") {
      ac::InterfaceOp interface;
      for (ac::InterfaceOp candidate :
           instance->getParentOfType<mlir::ModuleOp>()
               .getOps<ac::InterfaceOp>())
        if (candidate.getSymName() == endpoint.getInterface().getValue()) {
          interface = candidate;
          break;
        }
      ac::RoleOp role;
      if (interface)
        for (ac::RoleOp candidate : interface.getOps<ac::RoleOp>())
          if (candidate.getSymName() == endpoint.getRole().getValue()) {
            role = candidate;
            break;
          }
      if (!role)
        return lowerError(instance, "ACLOWER-TYPE-MISMATCH",
                          "endpoint role cannot be resolved for input port "
                          "lowering");
      expectedRole = role.getDual();
    }
    std::optional<unsigned> match;
    for (auto [index, port] : llvm::enumerate(record.ports())) {
      if (!used[index] && port.direction == direction &&
          port.interface == endpoint.getInterface().getValue() &&
          port.role == expectedRole) {
        if (match)
          return lowerError(instance, "ACLOWER-BINDING-AMBIGUOUS",
                            "binding '" + record.binding() +
                                "' has multiple ports matching endpoint " +
                                endpoint.getInterface().getValue() +
                                "::" + expectedRole);
        match = index;
      }
    }
    if (!match)
      return lowerError(instance, "ACLOWER-TYPE-MISMATCH",
                        "binding '" + record.binding() + "' has no exact " +
                            direction + " port for " +
                            endpoint.getInterface().getValue() +
                            "::" + expectedRole);
    used[*match] = true;
    endpoints.push_back({value, record.ports()[*match]});
    return mlir::success();
  };

  for (Value input : instance.getInputs())
    if (failed(planEndpoint(input, "input", planned.inputPorts)))
      return mlir::failure();
  for (Value output : instance.getOutputs())
    if (failed(planEndpoint(output, "output", planned.outputPorts)))
      return mlir::failure();
  if (llvm::any_of(used, [](bool value) { return !value; }))
    return lowerError(instance, "ACLOWER-TYPE-MISMATCH",
                      "binding '" + record.binding() +
                          "' exposes a port that is absent from the external "
                          "module signature");
  return mlir::success();
}

mlir::LogicalResult ACIRToACSimPass::planModule(ac::ModuleOp module,
                                                ModulePlan &planned) {
  FunctionType signature = module.getFunctionType();
  if (llvm::any_of(signature.getInputs(),
                   [](Type type) { return !isa<ac::FlowType>(type); })) {
    std::string printed;
    llvm::raw_string_ostream stream(printed);
    stream << signature;
    return lowerError(module, "ACLOWER-TYPE-MISMATCH",
                      "generated ACSim modules carry only structural Flow "
                      "arguments; module '@" +
                          module.getSymName() + "' has '" + stream.str() + "'");
  }

  OpBuilder builder(module->getContext());
  llvm::SmallVector<Attribute> staticValues;
  for (NamedAttribute named : module.getStaticParams())
    staticValues.push_back(named.getValue());
  planned.staticParams = builder.getArrayAttr(staticValues);
  planned.specialization = moduleFingerprint(module);

  llvm::SmallVector<PlacementPlan, 0> processes;
  llvm::DenseMap<Value, std::pair<std::string, bindings::PortBinding>>
      flowExports;
  llvm::DenseMap<Value, std::pair<std::string, bindings::PortBinding>>
      flowImports;
  llvm::StringSet<> arbitrationResources;
  module.walk([&](ac::ArbitrateOp arbiter) {
    for (Attribute candidate : arbiter.getCandidateResources())
      for (Attribute resource : cast<ArrayAttr>(candidate))
        arbitrationResources.insert(
            cast<FlatSymbolRefAttr>(resource).getValue());
  });
  ac::ReturnOp moduleReturn;
  for (Operation &operation : module.getBody().front()) {
    if (auto instance = dyn_cast<ac::InstanceOp>(operation)) {
      PlacementPlan placement;
      placement.kind = PlacementPlan::Kind::Instance;
      placement.name = instance.getSymName().str();
      if (failed(planInstanceTarget(instance, instance.getDefinition(),
                                    instance.getStaticArgs(), placement)))
        return mlir::failure();
      if (placement.targetIsPure) {
        if (instance.getNumResults() != 1)
          return lowerError(instance, "ACLOWER-TYPE-MISMATCH",
                            "pure external placement must produce exactly one "
                            "SSA result");
        if (!instance.getInputs().empty())
          return lowerError(instance, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                            "pure external SSA operands require typed graph "
                            "lowering");
        planned.pureCalls.push_back(
            {instance, instance.getResult(0), instance.getSymName().str(),
             placement.targetSymbol, placement.resultCppType});
        continue;
      }
      if (failed(planInstancePorts(instance, placement)))
        return mlir::failure();
      planned.placements.push_back(std::move(placement));
      continue;
    }
    if (auto queue = dyn_cast<ac::EventQueueOp>(operation)) {
      if (queue.getOrdering() != "time_then_sequence" ||
          queue.getDelayTicks() != 1)
        return lowerError(queue, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "native event queues require ordering "
                          "'time_then_sequence' and delay_ticks = 1");
      auto eventType = dyn_cast<ac::EventType>(queue.getPayload());
      auto elementCpp =
          eventType ? nativeQueueCppType(eventType.getElementType(), queue)
                    : std::nullopt;
      if (!elementCpp)
        return lowerError(queue, "ACLOWER-TYPE-MISMATCH",
                          "native event queue payload has no closed C++ "
                          "realization");
      std::string payloadSpelling;
      llvm::raw_string_ostream(payloadSpelling) << eventType.getElementType();
      llvm::json::Object typeDescriptor;
      typeDescriptor["contract_epoch"] = kEpoch;
      typeDescriptor["kind"] = "runtime_object";
      typeDescriptor["payload"] = payloadSpelling;
      typeDescriptor["ordering"] = queue.getOrdering().str();
      std::string typeFingerprint =
          fingerprintJson(llvm::json::Value(std::move(typeDescriptor)));
      std::string identity =
          "acir_event_queue_" +
          llvm::StringRef(typeFingerprint).drop_front(7).str();
      if (failed(typeSymbols.intern(
              queue, identity, "runtime_object",
              "gfsim::TimedEventQueue<" + *elementCpp + ">", typeFingerprint)))
        return mlir::failure();
      if (isa<ac::PacketType>(eventType.getElementType()) &&
          !nativePacketValueIdentities.contains(eventType.getElementType())) {
        llvm::json::Object valueDescriptor;
        valueDescriptor["contract_epoch"] = kEpoch;
        valueDescriptor["kind"] = "packet";
        valueDescriptor["payload"] = payloadSpelling;
        std::string valueFingerprint =
            fingerprintJson(llvm::json::Value(std::move(valueDescriptor)));
        std::string valueIdentity =
            "acir_packet_" +
            llvm::StringRef(valueFingerprint).drop_front(7).str();
        if (failed(typeSymbols.intern(queue, valueIdentity, "packet",
                                      *elementCpp, valueFingerprint)))
          return mlir::failure();
        nativePacketValueIdentities.try_emplace(eventType.getElementType(),
                                                valueIdentity);
      }
      PlacementPlan placement;
      placement.kind = PlacementPlan::Kind::RuntimeObject;
      placement.name = queue.getSymName().str();
      placement.targetSymbol = identity;
      placement.targetIsRuntimeObject = true;
      placement.eventQueue = queue;
      placement.staticArgs = builder.getArrayAttr(
          {builder.getI64IntegerAttr(queue.getCapacity())});
      llvm::json::Object specialization;
      specialization["contract_epoch"] = kEpoch;
      specialization["kind"] = "event_queue";
      specialization["type"] = typeFingerprint;
      specialization["capacity"] = queue.getCapacity();
      placement.specialization =
          fingerprintJson(llvm::json::Value(std::move(specialization)));
      placement.work = "gfsim::QueueRuntime::work";
      placement.xfer = "gfsim::QueueRuntime::xfer";
      placement.reset = "gfsim::QueueRuntime::reset";
      placement.validate = "gfsim::QueueRuntime::validate";
      planned.placements.push_back(std::move(placement));
      continue;
    }
    if (auto array = dyn_cast<ac::ArrayOp>(operation)) {
      PlacementPlan placement;
      placement.kind = PlacementPlan::Kind::Array;
      placement.name = array.getSymName().str();
      placement.shape.assign(array.getShape().begin(), array.getShape().end());
      // Homogeneous arrays require one exact specialization per element.
      DictionaryAttr first;
      for (Attribute element : array.getStaticArgs()) {
        auto arguments = dyn_cast<DictionaryAttr>(element);
        if (!arguments)
          return lowerError(array, "ACLOWER-ARRAY",
                            "array static arguments must be concrete "
                            "dictionaries");
        if (!first)
          first = arguments;
        else if (arguments != first)
          return lowerError(array, "ACLOWER-ARRAY",
                            "differently specialized array elements are "
                            "outside the v0.2 lowering stage; lower them as "
                            "ordered named members instead");
      }
      if (failed(planInstanceTarget(array, array.getDefinition(), first,
                                    placement)))
        return mlir::failure();
      if (placement.targetIsPure)
        return lowerError(array, "ACLOWER-OWNERSHIP",
                          "pure bindings lower to acsim.inline and cannot own "
                          "an ac.array placement");
      planned.placements.push_back(std::move(placement));
      continue;
    }
    if (auto collection = dyn_cast<ac::InstancesOp>(operation)) {
      for (auto [index, definitionAttribute] :
           llvm::enumerate(collection.getDefinitions())) {
        auto definition = cast<FlatSymbolRefAttr>(definitionAttribute);
        auto arguments =
            cast<DictionaryAttr>(collection.getStaticArgs()[index]);
        PlacementPlan placement;
        placement.kind = PlacementPlan::Kind::Instance;
        placement.name =
            cast<StringAttr>(collection.getNames()[index]).getValue().str();
        if (failed(planInstanceTarget(collection, definition.getValue(),
                                      arguments, placement)))
          return mlir::failure();
        if (placement.targetIsPure)
          return lowerError(collection, "ACLOWER-OWNERSHIP",
                            "pure bindings lower to acsim.inline and cannot "
                            "own an ac.instances placement");
        planned.placements.push_back(std::move(placement));
      }
      continue;
    }
    if (auto process = dyn_cast<ac::ProcessOp>(operation)) {
      PlacementPlan placement;
      placement.kind = PlacementPlan::Kind::Process;
      placement.name = process.getSymName().str();
      placement.process = process;
      processes.push_back(std::move(placement));
      continue;
    }
    if (auto queue = dyn_cast<ac::QueueOp>(operation)) {
      if (queue.getOrdering() != "fifo")
        return lowerError(queue, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "native queues require ordering 'fifo'; per_key "
                          "queues are not supported in v0.2");
      if (queue.getOwnership() != "exclusive")
        return lowerError(queue, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "native queues require exclusive ownership");
      if (queue.getDelayTicks() != 1)
        return lowerError(queue, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "native queues require delay_ticks = 1");
      if (queue.getWatermarksAttr())
        return lowerError(queue, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "configured queue watermarks are not supported in "
                          "v0.2 lowering");
      auto elementCpp = nativeQueueCppType(queue.getPayload(), queue);
      if (!elementCpp)
        return lowerError(queue, "ACLOWER-TYPE-MISMATCH",
                          "native queue payload has no closed C++ "
                          "realization");
      llvm::json::Object typeDescriptor;
      std::string payloadSpelling;
      llvm::raw_string_ostream(payloadSpelling) << queue.getPayload();
      typeDescriptor["contract_epoch"] = kEpoch;
      typeDescriptor["kind"] = "runtime_object";
      typeDescriptor["payload"] = payloadSpelling;
      typeDescriptor["byte_capacity"] =
          static_cast<bool>(queue.getByteCapacityAttr());
      std::string typeFingerprint =
          fingerprintJson(llvm::json::Value(std::move(typeDescriptor)));
      if (typeFingerprint.empty())
        return lowerError(queue, "ACLOWER-FINGERPRINT",
                          "failed to fingerprint native queue type");
      std::string identity =
          "acir_queue_" + llvm::StringRef(typeFingerprint).drop_front(7).str();
      if (failed(typeSymbols.intern(queue, identity, "runtime_object",
                                    "gfsim::Queue<" + *elementCpp + ">",
                                    typeFingerprint)))
        return mlir::failure();
      if (isa<ac::PacketType>(queue.getPayload()) &&
          !nativePacketValueIdentities.contains(queue.getPayload())) {
        llvm::json::Object valueDescriptor;
        valueDescriptor["contract_epoch"] = kEpoch;
        valueDescriptor["kind"] = "packet";
        valueDescriptor["payload"] = payloadSpelling;
        std::string valueFingerprint =
            fingerprintJson(llvm::json::Value(std::move(valueDescriptor)));
        if (valueFingerprint.empty())
          return lowerError(queue, "ACLOWER-FINGERPRINT",
                            "failed to fingerprint native packet value type");
        std::string valueIdentity =
            "acir_packet_" +
            llvm::StringRef(valueFingerprint).drop_front(7).str();
        if (failed(typeSymbols.intern(queue, valueIdentity, "packet",
                                      *elementCpp, valueFingerprint)))
          return mlir::failure();
        nativePacketValueIdentities.try_emplace(queue.getPayload(),
                                                valueIdentity);
      }

      PlacementPlan placement;
      placement.kind = PlacementPlan::Kind::RuntimeObject;
      placement.name = queue.getSymName().str();
      placement.targetSymbol = identity;
      placement.targetIsRuntimeObject = true;
      placement.queue = queue;
      llvm::SmallVector<Attribute> args{
          builder.getI64IntegerAttr(queue.getEntryCapacity())};
      if (queue.getByteCapacityAttr())
        args.push_back(builder.getI64IntegerAttr(*queue.getByteCapacity()));
      placement.staticArgs = builder.getArrayAttr(args);
      llvm::json::Object specialization;
      specialization["contract_epoch"] = kEpoch;
      specialization["kind"] = "queue";
      specialization["type"] = typeFingerprint;
      specialization["entry_capacity"] = queue.getEntryCapacity();
      if (queue.getByteCapacityAttr())
        specialization["byte_capacity"] = queue.getByteCapacity();
      placement.specialization =
          fingerprintJson(llvm::json::Value(std::move(specialization)));
      placement.work = "gfsim::QueueRuntime::work";
      placement.xfer = "gfsim::QueueRuntime::xfer";
      placement.reset = "gfsim::QueueRuntime::reset";
      placement.validate = "gfsim::QueueRuntime::validate";
      planned.placements.push_back(std::move(placement));
      continue;
    }
    if (auto exportOp = dyn_cast<ac::FlowExportOp>(operation)) {
      auto flow = cast<ac::FlowType>(exportOp.getFlow().getType());
      std::string accessorIdentity = "acir_flow_source_accessor_" +
                                     module.getSymName().str() + "_" +
                                     exportOp.getQueue().str();
      auto metadata = nativeFlowPort(exportOp, flow, "output", accessorIdentity,
                                     "flowSource");
      if (failed(metadata))
        return failure();
      flowExports[exportOp.getFlow()] = {exportOp.getQueue().str(),
                                         std::move(*metadata)};
      continue;
    }
    if (auto importOp = dyn_cast<ac::FlowImportOp>(operation)) {
      auto argument = dyn_cast<BlockArgument>(importOp.getFlow());
      if (!argument || argument.getOwner() != &module.getBody().front())
        return lowerError(importOp, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                          "native Flow import must consume a module argument");
      auto flow = cast<ac::FlowType>(importOp.getFlow().getType());
      std::string accessorIdentity = "acir_flow_sink_accessor_" +
                                     module.getSymName().str() + "_" +
                                     importOp.getQueue().str();
      auto metadata =
          nativeFlowPort(importOp, flow, "input", accessorIdentity, "flowSink");
      if (failed(metadata))
        return failure();
      flowImports[importOp.getFlow()] = {importOp.getQueue().str(),
                                         std::move(*metadata)};
      continue;
    }
    if (auto domain = dyn_cast<ac::TimeDomainOp>(operation)) {
      timeDomains.push_back(domain);
      continue;
    }
    if (auto resource = dyn_cast<ac::ResourceOp>(operation);
        resource && arbitrationResources.contains(resource.getSymName())) {
      // Capacity-1 arbitration resources are compile-time conflict tokens.
      // They intentionally have no ACSim owner, binding, or runtime object.
      continue;
    }
    if (auto returnOp = dyn_cast<ac::ReturnOp>(operation)) {
      moduleReturn = returnOp;
      continue;
    }
    return lowerError(&operation, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                      "operation '" + operation.getName().getStringRef() +
                          "' has no ACSim realization in the v0.2 lowering "
                          "stage (resources, address maps, views, "
                          "and instrumentation are rejected, "
                          "never silently dropped)");
  }

  llvm::sort(planned.placements,
             [](const PlacementPlan &left, const PlacementPlan &right) {
               return left.name < right.name;
             });
  auto resolveFlowAlias = [&](Value value) {
    for (size_t step = 0; step <= planned.placements.size(); ++step) {
      Value next;
      for (const PlacementPlan &candidate : planned.placements)
        for (auto [result, source] : candidate.flowAliases)
          if (result == value)
            next = source;
      if (!next)
        return value;
      value = next;
    }
    return Value();
  };
  const size_t endpointPlacementCount = planned.placements.size();
  llvm::SmallVector<PlacementPlan, 0> flowLinks;
  for (size_t targetIndex = 0; targetIndex < endpointPlacementCount;
       ++targetIndex) {
    PlacementPlan &target = planned.placements[targetIndex];
    for (const PortEndpointPlan &input : target.inputPorts) {
      Value inputSource = resolveFlowAlias(input.value);
      if (!inputSource)
        return lowerError(target.inputPorts.front().value.getDefiningOp(),
                          "ACLOWER-OWNERSHIP",
                          "native Flow pass-through contains a cycle");
      std::optional<unsigned> sourceIndex;
      const PortEndpointPlan *sourceEndpoint = nullptr;
      for (size_t candidateIndex = 0; candidateIndex < endpointPlacementCount;
           ++candidateIndex)
        for (const PortEndpointPlan &output :
             planned.placements[candidateIndex].outputPorts)
          if (output.value == inputSource) {
            sourceIndex = candidateIndex;
            sourceEndpoint = &output;
            break;
          }
      if (!sourceIndex)
        return lowerError(target.inputPorts.front().value.getDefiningOp(),
                          "ACLOWER-TYPE-MISMATCH",
                          "typed endpoint input has no lowered producer");
      BindingEdgePlan edge{*sourceIndex, static_cast<unsigned>(targetIndex)};
      edge.nativeFlow = input.nativeFlow;
      if (edge.nativeFlow) {
        const PlacementPlan &source = planned.placements[*sourceIndex];
        auto sourceModule = moduleIndexByName.find(source.targetSymbol);
        auto targetModule = moduleIndexByName.find(target.targetSymbol);
        if (sourceModule == moduleIndexByName.end() ||
            targetModule == moduleIndexByName.end())
          return lowerError(target.inputPorts.front().value.getDefiningOp(),
                            "ACLOWER-UNSUPPORTED-CONSTRUCT",
                            "native Flow endpoints must be concrete modules");
        for (const ModulePortPlan &port : modules[sourceModule->second].ports)
          if (port.nativeFlow && port.resultIndex >= 0 &&
              port.metadata.accessor == sourceEndpoint->metadata.accessor)
            edge.sourceChild = port.queue;
        for (const ModulePortPlan &port : modules[targetModule->second].ports)
          if (port.nativeFlow && port.inputIndex >= 0 &&
              port.metadata.accessor == input.metadata.accessor)
            edge.targetChild = port.queue;
        if (edge.sourceChild.empty() || edge.targetChild.empty())
          return lowerError(target.inputPorts.front().value.getDefiningOp(),
                            "ACLOWER-OWNERSHIP",
                            "native Flow endpoint has no boundary queue");

        auto flow = dyn_cast<ac::FlowType>(input.value.getType());
        auto payloadCpp =
            flow ? nativeQueueCppType(flow.getElementType(), planned.source)
                 : std::optional<std::string>();
        if (!payloadCpp)
          return lowerError(target.inputPorts.front().value.getDefiningOp(),
                            "ACLOWER-TYPE-MISMATCH",
                            "native Flow link payload has no C++ realization");
        std::string linkIdentity =
            "acir_queue_link_" +
            llvm::StringRef(bindings::sha256Fingerprint(*payloadCpp))
                .drop_front(7)
                .str();
        if (failed(typeSymbols.intern(planned.source, linkIdentity,
                                      "runtime_object",
                                      "gfsim::QueueLink<" + *payloadCpp + ">")))
          return failure();
        PlacementPlan link;
        link.kind = PlacementPlan::Kind::RuntimeObject;
        link.name =
            llvm::formatv("zz_flow_link_{0:08}", planned.bindingEdges.size())
                .str();
        link.targetSymbol = std::move(linkIdentity);
        link.targetIsRuntimeObject = true;
        link.staticArgs = builder.getArrayAttr({});
        // Specialization identity describes construction, not placement.
        // QueueLink has no static arguments and its payload is already part of
        // targetSymbol, so every link with this target shares one fingerprint.
        llvm::json::Object linkSpecialization;
        linkSpecialization["contract_epoch"] = kEpoch;
        linkSpecialization["kind"] = "flow_link";
        linkSpecialization["type"] = link.targetSymbol;
        link.specialization = fingerprintJson(
            llvm::json::Value(std::move(linkSpecialization)));
        link.work = "gfsim::QueueLinkRuntime::work";
        link.xfer = "gfsim::QueueLinkRuntime::xfer";
        link.reset = "gfsim::QueueLinkRuntime::reset";
        link.validate = "gfsim::QueueLinkRuntime::validate";
        link.flowLink = true;
        edge.linkPlacement = endpointPlacementCount + flowLinks.size();
        flowLinks.push_back(std::move(link));
      }
      planned.bindingEdges.push_back(std::move(edge));
    }
  }
  for (PlacementPlan &link : flowLinks)
    planned.placements.push_back(std::move(link));
  llvm::sort(processes,
             [](const PlacementPlan &left, const PlacementPlan &right) {
               return left.name < right.name;
             });
  llvm::sort(planned.pureCalls,
             [](const PureCallPlan &left, const PureCallPlan &right) {
               return left.name < right.name;
             });
  for (auto &process : processes)
    planned.placements.push_back(std::move(process));
  for (auto [targetIndex, target] : llvm::enumerate(planned.placements)) {
    if (target.kind != PlacementPlan::Kind::Process)
      continue;
    for (Value capture : target.process.getCaptures()) {
      std::optional<unsigned> sourceIndex;
      for (auto [candidateIndex, candidate] :
           llvm::enumerate(planned.placements))
        if (llvm::any_of(candidate.outputPorts,
                         [&](const PortEndpointPlan &output) {
                           return output.value == capture;
                         })) {
          sourceIndex = candidateIndex;
          break;
        }
      if (!sourceIndex)
        return lowerError(target.process, "ACLOWER-TYPE-MISMATCH",
                          "process capture has no lowered typed producer");
      planned.bindingEdges.push_back(
          {*sourceIndex, static_cast<unsigned>(targetIndex)});
    }
    llvm::StringSet<> referencedQueues;
    llvm::StringSet<> consumedEventQueues;
    target.process.walk([&](Operation *operation) {
      if (auto transfer = dyn_cast<ac::TryTransferOp>(operation)) {
        referencedQueues.insert(transfer.getSource());
        referencedQueues.insert(transfer.getDestination());
      } else if (auto send = dyn_cast<ac::TrySendOp>(operation))
        referencedQueues.insert(send.getQueue());
      else if (auto recv = dyn_cast<ac::TryRecvOp>(operation))
        referencedQueues.insert(recv.getQueue());
      else if (auto peek = dyn_cast<ac::PeekOp>(operation))
        referencedQueues.insert(peek.getQueue());
      else if (auto space = dyn_cast<ac::SpaceOp>(operation))
        referencedQueues.insert(space.getQueue());
      else if (auto await = dyn_cast<ac::AwaitQueueOp>(operation))
        referencedQueues.insert(await.getQueue());
      else if (auto schedule = dyn_cast<ac::ScheduleOp>(operation))
        referencedQueues.insert(schedule.getTarget());
      else if (auto recv = dyn_cast<ac::TryEventOp>(operation)) {
        referencedQueues.insert(recv.getEventQueue());
        consumedEventQueues.insert(recv.getEventQueue());
      } else if (auto await = dyn_cast<ac::AwaitEventOp>(operation)) {
        referencedQueues.insert(await.getEventQueue());
        consumedEventQueues.insert(await.getEventQueue());
      }
    });
    for (const auto &queueName : referencedQueues) {
      auto queue =
          llvm::find_if(planned.placements, [&](const auto &candidate) {
            return candidate.kind == PlacementPlan::Kind::RuntimeObject &&
                   candidate.name == queueName.getKey();
          });
      if (queue == planned.placements.end())
        return lowerError(target.process, "ACLOWER-OWNERSHIP",
                          "process queue reference has no native owner");
      planned.bindingEdges.push_back(
          {static_cast<unsigned>(queue - planned.placements.begin()),
           static_cast<unsigned>(targetIndex),
           !queue->eventQueue ||
               consumedEventQueues.contains(queueName.getKey())});
    }
  }

  if (!moduleReturn ||
      moduleReturn.getNumOperands() != signature.getNumResults())
    return lowerError(module, "ACLOWER-TYPE-MISMATCH",
                      "module return arity must match the declared result "
                      "interface");
  for (auto &[value, endpoint] : flowImports) {
    auto argument = cast<BlockArgument>(value);
    ModulePortPlan port;
    port.source = value;
    port.name =
        llvm::formatv("flow_input_{0:08}", argument.getArgNumber()).str();
    port.metadata = endpoint.second;
    port.queue = endpoint.first;
    port.localAccessor = endpoint.second.accessor;
    port.nativeFlow = true;
    port.inputIndex = argument.getArgNumber();
    std::string moduleAccessor = "acir_module_flow_accessor_" +
                                 module.getSymName().str() + "_" + port.name;
    if (failed(
            typeSymbols.intern(module, moduleAccessor, "accessor", port.name)))
      return failure();
    port.metadata.accessor = std::move(moduleAccessor);
    planned.ports.push_back(std::move(port));
  }
  for (auto [index, operand] : llvm::enumerate(moduleReturn.getOperands())) {
    if (isa<ac::FlowType>(operand.getType())) {
      if (auto exported = flowExports.find(operand);
          exported != flowExports.end()) {
        ModulePortPlan port;
        port.source = operand;
        port.name = llvm::formatv("flow_output_{0:08}", index).str();
        port.metadata = exported->second.second;
        port.queue = exported->second.first;
        port.localAccessor = exported->second.second.accessor;
        port.nativeFlow = true;
        port.resultIndex = index;
        std::string moduleAccessor = "acir_module_flow_accessor_" +
                                     module.getSymName().str() + "_" +
                                     port.name;
        if (failed(typeSymbols.intern(module, moduleAccessor, "accessor",
                                      port.name)))
          return failure();
        port.metadata.accessor = std::move(moduleAccessor);
        planned.ports.push_back(std::move(port));
        continue;
      }
      auto argument = dyn_cast<BlockArgument>(operand);
      if (argument && argument.getOwner() == &module.getBody().front()) {
        planned.flowAliases.push_back(
            {static_cast<unsigned>(index), argument.getArgNumber()});
        continue;
      }
      return lowerError(moduleReturn, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                        "Flow result must resolve to flow.export or a direct "
                        "pass-through module argument");
    }
    const PortEndpointPlan *exportedPort = nullptr;
    for (const PlacementPlan &placement : planned.placements)
      for (const PortEndpointPlan &port : placement.outputPorts)
        if (port.value == operand) {
          exportedPort = &port;
          break;
        }
    if (exportedPort) {
      planned.ports.push_back({operand,
                               llvm::formatv("port_{0:08}", index).str(),
                               exportedPort->metadata});
      continue;
    }
    const PureCallPlan *producer = nullptr;
    for (const PureCallPlan &call : planned.pureCalls)
      if (call.result == operand) {
        producer = &call;
        break;
      }
    if (!producer)
      return lowerError(
          moduleReturn, "ACLOWER-UNSUPPORTED-CONSTRUCT",
          "module result " + llvm::Twine(index) +
              " must be a typed endpoint export or be produced by an exact "
              "pure external binding");
    ModuleResultPlan result;
    result.source = operand;
    result.name = llvm::formatv("result_{0:08}", index).str();
    result.cppType = producer->cppType;
    planned.results.push_back(std::move(result));
  }
  llvm::sort(planned.ports,
             [](const ModulePortPlan &left, const ModulePortPlan &right) {
               return left.name < right.name;
             });
  return mlir::success();
}

mlir::LogicalResult ACIRToACSimPass::planProcesses(mlir::ModuleOp input) {
  bool hasProcess = false;
  input.walk([&](ac::ProcessOp) { hasProcess = true; });
  if (!hasProcess)
    return mlir::success();

  auto plans = planProcessState(input);
  if (failed(plans))
    return mlir::failure();
  if (failed(verifyProcessStatePlan(*plans)))
    return mlir::failure();
  processPlans = std::move(*plans);
  auto serializedPlans = serializeProcessStatePlan(*processPlans);
  if (!serializedPlans) {
    llvm::consumeError(serializedPlans.takeError());
    return lowerError(input, "ACLOWER-FINGERPRINT",
                      "failed to serialize the canonical process-state plan");
  }
  processPlanBytes = std::move(*serializedPlans);

  generatedCalleeIdentities.resize(processPlans->callees().size());
  for (const ProcessGeneratedCalleePlan &callee : processPlans->callees()) {
    llvm::StringRef symbol = callee.symbol();
    symbol.consume_front("@");
    generatedCalleeIdentities[callee.id().value()] = symbol.str();
    if (failed(typeSymbols.intern(input, symbol, "implementation", callee.cpp(),
                                  callee.fingerprint())))
      return mlir::failure();
  }
  for (const ProcessStatePlan &process : processPlans->processes()) {
    for (const ProcessWakePlan &wake : process.wakes()) {
      llvm::StringRef typeKey = wake.typeKey();
      typeKey.consume_front("@");
      wakeTypeIdentities[typeKey] = typeKey.str();
    }
  }
  for (const auto &[typeKey, identity] : wakeTypeIdentities) {
    llvm::StringRef cppName = identity;
    cppName.consume_front("acir_");
    std::string cpp = ("acir::generated::" + cppName).str();
    if (failed(typeSymbols.intern(input, identity, "wake", cpp)))
      return mlir::failure();
  }
  valueTypeIdentities.resize(processPlans->valueTypes().size());
  for (const ProcessValueTypePlan &valueType : processPlans->valueTypes()) {
    llvm::StringRef symbol = valueType.symbol();
    symbol.consume_front("@");
    valueTypeIdentities[valueType.id().value()] = symbol.str();
    llvm::StringRef kind =
        valueType.kind() == ProcessValueTypeKind::Packet ? "packet" : "value";
    if (failed(typeSymbols.intern(input, symbol, kind, valueType.cpp(),
                                  valueType.fingerprint())))
      return mlir::failure();
  }

  // Attach plan-derived fairness caps to the module placements.
  for (ModulePlan &module : modules)
    for (PlacementPlan &placement : module.placements) {
      if (placement.kind != PlacementPlan::Kind::Process)
        continue;
      std::string key = "@" + module.name + "::@" + placement.name;
      const ProcessStatePlan *plan = processPlans->lookupByDefinitionKey(key);
      if (!plan)
        return lowerError(placement.process, "ACLOWER-PROCESS-STATE",
                          "process-state plan is missing process '@" +
                              placement.name + "'");
      placement.processDefinitionKey = key;
      placement.fairnessCap = plan->fairnessWork();
      placement.specialization = processFingerprint(module, placement);
      if (placement.specialization.empty())
        return lowerError(placement.process, "ACLOWER-FINGERPRINT",
                          "failed to fingerprint process specialization");
    }
  return mlir::success();
}

mlir::LogicalResult ACIRToACSimPass::plan(mlir::ModuleOp input) {
  auto epoch = input->getAttrOfType<StringAttr>("ac.contract_epoch");
  if (!epoch || epoch.getValue() != kEpoch)
    return lowerError(input, "ACLOWER-EPOCH-MISMATCH",
                      "ac-lower-to-acsim requires ac.contract_epoch exactly "
                      "\"0.2\"");
  auto frozen = input->getAttrOfType<BoolAttr>("ac.topology_frozen");
  auto freezeEpoch = input->getAttrOfType<StringAttr>("ac.freeze_epoch");
  if (!frozen || !frozen.getValue() || !freezeEpoch ||
      freezeEpoch.getValue() != kEpoch)
    return lowerError(input, "ACLOWER-EPOCH-MISMATCH",
                      "ac-lower-to-acsim requires a topology-frozen v0.2 "
                      "model; run ac-freeze-topology first");
  auto frozenOwners = input->getAttrOfType<ArrayAttr>("ac.frozen_owners");
  if (!frozenOwners)
    return lowerError(input, "ACLOWER-OWNERSHIP",
                      "frozen model is missing its canonical owner manifest");
  for (Attribute owner : frozenOwners) {
    auto record = dyn_cast<DictionaryAttr>(owner);
    auto path = record ? record.getAs<StringAttr>("path") : StringAttr();
    if (!path || !frozenOwnerPaths.insert(path.getValue()).second)
      return lowerError(input, "ACLOWER-OWNERSHIP",
                        "frozen owner manifest has a missing or duplicate "
                        "canonical path");
  }
  if (options.profile.empty() || options.target.empty())
    return lowerError(input, "ACLOWER-PROFILE",
                      "ac-lower-to-acsim requires an exact static build "
                      "profile and toolchain target");

  unsigned selectedCount = 0;
  for (auto system : input.getOps<ac::SystemOp>()) {
    if (!system.getSelected())
      continue;
    ++selectedCount;
    selectedSystem = system;
  }
  if (selectedCount != 1)
    return lowerError(input, "ACLOWER-OWNERSHIP",
                      "ac-lower-to-acsim requires exactly one selected "
                      "ac.system");

  // Inventory concrete modules, externals, and top-level declarations.
  for (Operation &operation : *input.getBody()) {
    if (auto module = dyn_cast<ac::ModuleOp>(operation)) {
      moduleIndexByName[module.getSymName()] = modules.size();
      ModulePlan planned;
      planned.source = module;
      planned.name = module.getSymName().str();
      modules.push_back(std::move(planned));
      continue;
    }
    if (auto external = dyn_cast<ac::ModuleExternOp>(operation)) {
      externByName[external.getSymName()] = external;
      continue;
    }
    if (isa<ac::ModuleGeneratedOp>(operation))
      return lowerError(&operation, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                        "generator-based module declarations are outside the "
                        "v0.2 lowering stage");
    if (isa<ac::SystemOp, ac::TypeScopeOp, ac::TypeAliasOp, ac::StructOp,
            ac::EnumOp, ac::UnionOp, ac::PacketOp, ac::TransactionOp,
            ac::InterfaceOp, ac::ProtocolOp>(operation))
      continue; // Pure declarations are fully resolved before lowering.
    return lowerError(&operation, "ACLOWER-UNSUPPORTED-CONSTRUCT",
                      "top-level operation '" +
                          operation.getName().getStringRef() +
                          "' has no ACSim realization in the v0.2 lowering "
                          "stage");
  }

  llvm::sort(modules, [](const ModulePlan &left, const ModulePlan &right) {
    return left.name < right.name;
  });
  moduleIndexByName.clear();
  for (auto [index, module] : llvm::enumerate(modules))
    moduleIndexByName[module.name] = index;

  llvm::SmallVector<uint32_t> dependencyCount(modules.size());
  llvm::SmallVector<llvm::SmallVector<unsigned, 2>> parentsByChild(
      modules.size());
  for (auto [ownerIndex, module] : llvm::enumerate(modules)) {
    llvm::SmallSet<unsigned, 8> dependencies;
    auto addDependency = [&](llvm::StringRef definition) {
      auto target = moduleIndexByName.find(definition);
      if (target != moduleIndexByName.end())
        dependencies.insert(target->second);
    };
    for (Operation &operation : module.source.getBody().front()) {
      if (auto instance = dyn_cast<ac::InstanceOp>(operation))
        addDependency(instance.getDefinition());
      else if (auto array = dyn_cast<ac::ArrayOp>(operation))
        addDependency(array.getDefinition());
      else if (auto collection = dyn_cast<ac::InstancesOp>(operation))
        for (Attribute definition : collection.getDefinitions())
          addDependency(cast<FlatSymbolRefAttr>(definition).getValue());
    }
    dependencyCount[ownerIndex] = dependencies.size();
    for (unsigned childIndex : dependencies)
      parentsByChild[childIndex].push_back(ownerIndex);
  }
  std::set<std::pair<std::string, unsigned>> readyModules;
  for (auto [index, module] : llvm::enumerate(modules))
    if (dependencyCount[index] == 0)
      readyModules.emplace(module.name, index);
  llvm::SmallVector<ModulePlan, 0> orderedModules;
  orderedModules.reserve(modules.size());
  while (!readyModules.empty()) {
    unsigned childIndex = readyModules.begin()->second;
    readyModules.erase(readyModules.begin());
    orderedModules.push_back(std::move(modules[childIndex]));
    for (unsigned parentIndex : parentsByChild[childIndex])
      if (--dependencyCount[parentIndex] == 0)
        readyModules.emplace(modules[parentIndex].name, parentIndex);
  }
  if (orderedModules.size() != modules.size())
    return lowerError(input, "ACLOWER-OWNERSHIP",
                      "module instantiation cycle cannot produce canonical "
                      "ACSim module order");
  modules = std::move(orderedModules);
  moduleIndexByName.clear();
  for (auto [index, module] : llvm::enumerate(modules))
    moduleIndexByName[module.name] = index;

  // The selected root must be a concrete generated module.
  llvm::StringRef rootName = selectedSystem.getRoot();
  if (!moduleIndexByName.count(rootName))
    return lowerError(selectedSystem, "ACLOWER-OWNERSHIP",
                      "selected system root '@" + rootName +
                          "' must be a concrete ac.module");

  // Resolve exact bindings in memory (shared contract with
  // ac-resolve-gfsim-bindings; no lock file round-trip).
  ResolveBindingsPassOptions resolveOptions;
  resolveOptions.candidates = options.candidates;
  resolveOptions.requests = options.requests;
  resolveOptions.profile = options.profile;
  resolveOptions.target = options.target;
  auto resolved = resolveModuleBindings(input, resolveOptions);
  if (!resolved) {
    input.emitError() << llvm::toString(resolved.takeError());
    return mlir::failure();
  }
  resolution = std::move(*resolved);

  // Module references may point forward in canonical symbol order.  Freeze
  // every target identity before any body consults it so spelling never
  // constrains the legal instantiation graph.
  OpBuilder identityBuilder(input.getContext());
  for (ModulePlan &module : modules) {
    llvm::SmallVector<Attribute> staticValues;
    for (NamedAttribute named : module.source.getStaticParams())
      staticValues.push_back(named.getValue());
    module.staticParams = identityBuilder.getArrayAttr(staticValues);
    module.specialization = moduleFingerprint(module.source);
  }

  // Plan every concrete module body.
  for (auto [index, module] : llvm::enumerate(modules))
    if (failed(planModule(module.source, modules[index])))
      return mlir::failure();

  // Topology integrity and all grant-provenance checks above operate on the
  // exact frozen ACIR.  Only after those checks do we expand the pure arbiter
  // into ordinary Boolean SSA for ProcessState planning and emission.
  if (failed(lowerArbiters(input)) || failed(planProcesses(input)))
    return mlir::failure();

  // Intern every binding-record realization identity.
  for (const bindings::ResolvedBinding &selection : resolution->selections()) {
    const bindings::BindingRecord &record = selection.record();
    if (failed(typeSymbols.intern(input, record.componentSchema(), "schema",
                                  record.componentSchema(),
                                  record.componentSchemaFingerprint())) ||
        failed(
            typeSymbols.intern(input, record.implementation(), "implementation",
                               record.implementation(),
                               record.providerImplementationFingerprint())) ||
        failed(typeSymbols.intern(input, record.provider(), "provider",
                                  record.provider())) ||
        failed(typeSymbols.intern(input, record.cppType(), "value",
                                  record.cppType())))
      return mlir::failure();
    for (const bindings::PortBinding &port : record.ports())
      if (failed(typeSymbols.intern(input, port.accessor, "accessor",
                                    port.accessor)) ||
          failed(typeSymbols.intern(input, port.interface, "interface",
                                    port.interface)) ||
          failed(typeSymbols.intern(input, port.payload, "packet",
                                    port.payload)) ||
          failed(typeSymbols.intern(input, port.protocol, "protocol",
                                    port.protocol)) ||
          failed(typeSymbols.intern(input, port.role, "role", port.role)) ||
          failed(typeSymbols.intern(input, port.timeDomain, "time_domain",
                                    port.timeDomain)))
        return mlir::failure();
    for (const bindings::ResourceBinding &resource : record.resources())
      if (failed(typeSymbols.intern(input, resource.accessor, "accessor",
                                    resource.accessor)) ||
          failed(typeSymbols.intern(input, resource.resource, "resource",
                                    resource.resource)) ||
          failed(typeSymbols.intern(input, resource.role, "role",
                                    resource.role)) ||
          failed(typeSymbols.intern(input, resource.timeDomain, "time_domain",
                                    resource.timeDomain)))
        return mlir::failure();
    for (const bindings::ResultBinding &result : record.results())
      if (failed(typeSymbols.intern(input, result.cppType, "value",
                                    result.cppType)))
        return mlir::failure();
    for (const bindings::ActivationSourceBinding &source :
         record.activationSources())
      if (failed(typeSymbols.intern(input, source.kind, "wake", source.kind)))
        return mlir::failure();
  }
  llvm::sort(timeDomains, [](ac::TimeDomainOp left, ac::TimeDomainOp right) {
    return left.getSymName() < right.getSymName();
  });
  for (ac::TimeDomainOp domain : timeDomains)
    if (failed(typeSymbols.internTimeDomain(domain)))
      return mlir::failure();
  if (llvm::any_of(
          modules,
          [](const ModulePlan &module) { return !module.results.empty(); }) &&
      failed(typeSymbols.intern(input, kResultRoleIdentity, "role",
                                "acsim::ResultRole")))
    return mlir::failure();
  if (failed(typeSymbols.finalize(input)))
    return mlir::failure();

  // Binding symbols must not collide with type or module symbols.
  for (const bindings::ResolvedBinding &selection : resolution->selections()) {
    llvm::StringRef binding = selection.record().binding();
    if (typeSymbols.symbolFor(binding).data() != nullptr ||
        moduleIndexByName.count(binding))
      return lowerError(input, "ACLOWER-BINDING-AMBIGUOUS",
                        "binding identity '" + binding +
                            "' collides with a type or module symbol");
  }

  // Fingerprints over exact inputs, computed before any mutation.
  std::string frozenText;
  {
    llvm::raw_string_ostream output(frozenText);
    input.print(output);
  }
  frozenAcirFingerprint = bindings::sha256Fingerprint(frozenText);
  bindingLockFingerprint = resolution->lockFingerprint().str();

  llvm::json::Array providers;
  llvm::json::Array schemas;
  {
    std::map<std::string, bool> uniqueProviders;
    std::map<std::string, bool> uniqueSchemas;
    for (const bindings::ResolvedBinding &selection :
         resolution->selections()) {
      uniqueProviders[selection.record().provider().str()] = true;
      uniqueSchemas[selection.record().componentSchema().str()] = true;
    }
    for (auto &[identity, unused] : uniqueProviders)
      providers.push_back(identity);
    for (auto &[identity, unused] : uniqueSchemas)
      schemas.push_back(identity);
  }
  providerFingerprint =
      fingerprintJson(llvm::json::Value(std::move(providers)));
  schemaSetFingerprint = fingerprintJson(llvm::json::Value(std::move(schemas)));
  profileFingerprint = fingerprintJson(llvm::json::Value(options.profile));
  toolchainFingerprint = fingerprintJson(llvm::json::Value(options.target));
  if (providerFingerprint.empty() || schemaSetFingerprint.empty() ||
      profileFingerprint.empty() || toolchainFingerprint.empty())
    return lowerError(input, "ACLOWER-FINGERPRINT",
                      "failed to derive canonical model fingerprints");

  // Deterministic owner/runtime expansion over the planned structure.
  llvm::SmallSet<unsigned, 8> active;
  expandModule(moduleIndexByName.lookup(rootName),
               selectedSystem.getRootName().str(), active);
  if (expansionCycle)
    return lowerError(input, "ACLOWER-OWNERSHIP",
                      "module instantiation cycle cannot produce canonical "
                      "ACSim ownership order");
  const uint64_t maxExpandedRows =
      options.maxExpandedRows != 0 ? options.maxExpandedRows : kMaxExpandedRows;
  if (constructionOrder.size() > maxExpandedRows ||
      runtimeRows.size() > maxExpandedRows)
    return lowerError(input, "ACLOWER-DISPATCH",
                      "expanded hierarchy exceeds the v0.2 capability bound");
  if (llvm::any_of(constructionOrder,
                   [&](const std::string &path) {
                     llvm::StringRef leaf(path);
                     leaf = leaf.rsplit('.').second;
                     return !leaf.starts_with("zz_flow_link_") &&
                            !frozenOwnerPaths.contains(path);
                   }) ||
      !frozenOwnerPaths.contains(selectedSystem.getRootName()))
    return lowerError(input, "ACLOWER-OWNERSHIP",
                      "planned ACSim hierarchy paths do not exactly match "
                      "the frozen owner manifest");
  return mlir::success();
}

void ACIRToACSimPass::expandModule(unsigned moduleIndex, std::string pathPrefix,
                                   llvm::SmallSet<unsigned, 8> &active) {
  ModulePlan &module = modules[moduleIndex];
  active.insert(moduleIndex);
  for (auto [placementIndex, placement] : llvm::enumerate(module.placements)) {
    auto elementPath = [&](llvm::ArrayRef<int64_t> indices) {
      std::string path = pathPrefix;
      path.push_back('.');
      path.append(placement.name);
      llvm::raw_string_ostream stream(path);
      for (int64_t index : indices)
        stream << '[' << index << ']';
      return path;
    };
    auto expandOne = [&](llvm::ArrayRef<int64_t> indices) {
      std::string path = elementPath(indices);
      constructionOrder.push_back(path);
      if (placement.kind == PlacementPlan::Kind::Process ||
          placement.kind == PlacementPlan::Kind::RuntimeObject ||
          placement.targetIsBinding) {
        RuntimeRow row;
        row.moduleIndex = moduleIndex;
        row.placementIndex = placementIndex;
        row.contextPath = pathPrefix;
        row.path = path;
        row.indices.assign(indices.begin(), indices.end());
        runtimeRows.push_back(std::move(row));
        return;
      }
      unsigned targetIndex = moduleIndexByName.lookup(placement.targetSymbol);
      if (active.contains(targetIndex)) {
        // An instantiation cycle can never produce canonical ACSim.
        expansionCycle = true;
        constructionOrder.pop_back();
        return;
      }
      expandModule(targetIndex, std::move(path), active);
    };

    if (placement.kind == PlacementPlan::Kind::Array) {
      uint64_t volume = 1;
      for (int64_t extent : placement.shape) {
        if (extent == 0) {
          volume = 0;
          break;
        }
        volume *= static_cast<uint64_t>(extent);
      }
      for (uint64_t ordinal = 0; ordinal < volume; ++ordinal) {
        llvm::SmallVector<int64_t, 2> indices(placement.shape.size(), 0);
        uint64_t remainder = ordinal;
        for (size_t dimension = placement.shape.size(); dimension > 0;
             --dimension) {
          uint64_t extent =
              static_cast<uint64_t>(placement.shape[dimension - 1]);
          indices[dimension - 1] = static_cast<int64_t>(remainder % extent);
          remainder /= extent;
        }
        expandOne(indices);
      }
      continue;
    }
    expandOne({});
  }
  active.erase(moduleIndex);
}

// ---------------------------------------------------------------------------
// Emission
// ---------------------------------------------------------------------------

void appendOccurrenceKey(llvm::raw_ostream &stream,
                         const ProcessOccurrenceId &occurrence) {
  stream << static_cast<unsigned>(occurrence.kind()) << ':';
  switch (occurrence.kind()) {
  case ProcessOccurrenceKind::Original: {
    const ProcessOriginalOccurrence &original = occurrence.original();
    stream << original.operationPath() << '[';
    for (const ProcessCallSitePlan &callSite : original.callSites()) {
      stream << callSite.operationPath() << '(';
      llvm::interleaveComma(callSite.iterationVector(), stream);
      stream << ")";
    }
    stream << "](";
    llvm::interleaveComma(original.iterationVector(), stream);
    stream << ')';
    break;
  }
  case ProcessOccurrenceKind::SyntheticLoop:
    appendOccurrenceKey(stream, occurrence.syntheticLoop().anchor());
    stream << ":loop:"
           << static_cast<unsigned>(occurrence.syntheticLoop().phase());
    break;
  case ProcessOccurrenceKind::SyntheticWrapper:
    appendOccurrenceKey(stream, occurrence.syntheticWrapper().anchor());
    stream << ":wrapper:" << occurrence.syntheticWrapper().transition().value()
           << ':' << occurrence.syntheticWrapper().slot().value() << ':'
           << static_cast<unsigned>(occurrence.syntheticWrapper().direction());
    break;
  case ProcessOccurrenceKind::SyntheticConstant:
    appendOccurrenceKey(stream, occurrence.syntheticConstant().anchor());
    stream << ":constant:" << occurrence.syntheticConstant().constant();
    break;
  }
}

std::string plannedValueKey(const ProcessPlannedValue &value) {
  std::string key;
  llvm::raw_string_ostream stream(key);
  stream << static_cast<unsigned>(value.kind()) << ':';
  switch (value.kind()) {
  case ProcessPlannedValueKind::Original:
    appendOccurrenceKey(stream, value.original().occurrence());
    stream << ':' << value.original().coordinate().ownerPath() << ':'
           << value.original().coordinate().index();
    break;
  case ProcessPlannedValueKind::Capture:
    stream << value.capture().capture().value();
    break;
  case ProcessPlannedValueKind::LiveSlot:
    stream << value.liveSlot().slot().value();
    break;
  case ProcessPlannedValueKind::Synthetic:
    appendOccurrenceKey(stream, value.synthetic().occurrence());
    stream << ':' << value.synthetic().coordinate().ownerPath() << ':'
           << value.synthetic().coordinate().index();
    break;
  case ProcessPlannedValueKind::Constant:
    stream << value.constant().value();
    break;
  }
  return key;
}

void ACIRToACSimPass::emitProcessBody(
    OpBuilder &builder, const PlacementPlan &placement,
    const llvm::DenseMap<Value, Value> &moduleValues,
    const llvm::StringMap<Value> &queueOwners) {
  MLIRContext *context = builder.getContext();
  const ProcessStatePlan *plan =
      processPlans->lookupByDefinitionKey(placement.processDefinitionKey);
  assert(plan && "process placement must reference its validated public plan");

  llvm::SmallVector<Attribute> pcs;
  for (const ProcessPcPlan &pc : plan->pcs())
    pcs.push_back(FlatSymbolRefAttr::get(context, pc.name()));
  llvm::SmallVector<Attribute> liveSlots;
  for (const ProcessLiveSlotPlan &slot : plan->liveSlots()) {
    llvm::StringRef identity = valueTypeIdentities[slot.storageType().value()];
    auto type = acsim::ValueType::get(
        context,
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(identity)));
    liveSlots.push_back(builder.getDictionaryAttr(
        {builder.getNamedAttr("name", builder.getStringAttr(slot.name())),
         builder.getNamedAttr("type", TypeAttr::get(type))}));
  }
  llvm::SmallVector<Value> captures;
  llvm::SmallVector<Attribute> captureNames;
  for (const ProcessCapturePlan &capture : plan->captures()) {
    Value lowered = moduleValues.lookup(capture.operand());
    assert(lowered && "validated process capture must be projected");
    captures.push_back(lowered);
    captureNames.push_back(builder.getStringAttr(capture.name()));
  }
  std::vector<std::pair<std::string, std::string>> referencedQueues;
  llvm::StringSet<> seenQueues;
  ac::ProcessOp sourceProcess = placement.process;
  sourceProcess.walk([&](Operation *operation) {
    auto addQueueReference = [&](FlatSymbolRefAttr reference) {
      if (!reference || !seenQueues.insert(reference.getValue()).second)
        return;
      Operation *queue =
          SymbolTable::lookupNearestSymbolFrom(operation, reference);
      if (!isa_and_nonnull<ac::QueueOp, ac::EventQueueOp>(queue))
        if (auto owner = operation->getParentOfType<ac::ModuleOp>())
          for (Operation &candidate : owner.getBody().front())
            if (isa<ac::QueueOp, ac::EventQueueOp>(candidate) &&
                candidate
                        .getAttrOfType<StringAttr>(
                            SymbolTable::getSymbolAttrName())
                        .getValue() == reference.getValue()) {
              queue = &candidate;
              break;
            }
      assert(queue && "validated queue reference must resolve");
      llvm::StringRef path = isa<ac::QueueOp>(queue)
                                 ? cast<ac::QueueOp>(queue).getPath()
                                 : cast<ac::EventQueueOp>(queue).getPath();
      referencedQueues.emplace_back(path.str(), reference.getValue().str());
    };
    if (auto transfer = dyn_cast<ac::TryTransferOp>(operation)) {
      addQueueReference(transfer.getSourceAttr());
      addQueueReference(transfer.getDestinationAttr());
      return;
    }
    FlatSymbolRefAttr reference;
    if (auto send = dyn_cast<ac::TrySendOp>(operation))
      reference = send.getQueueAttr();
    else if (auto recv = dyn_cast<ac::TryRecvOp>(operation))
      reference = recv.getQueueAttr();
    else if (auto peek = dyn_cast<ac::PeekOp>(operation))
      reference = peek.getQueueAttr();
    else if (auto space = dyn_cast<ac::SpaceOp>(operation))
      reference = space.getQueueAttr();
    else if (auto await = dyn_cast<ac::AwaitQueueOp>(operation))
      reference = await.getQueueAttr();
    else if (auto schedule = dyn_cast<ac::ScheduleOp>(operation))
      reference = schedule.getTargetAttr();
    else if (auto recv = dyn_cast<ac::TryEventOp>(operation))
      reference = recv.getEventQueueAttr();
    else if (auto await = dyn_cast<ac::AwaitEventOp>(operation))
      reference = await.getEventQueueAttr();
    addQueueReference(reference);
  });
  llvm::sort(referencedQueues);
  for (const auto &[path, name] : referencedQueues) {
    Value owner = queueOwners.lookup(name);
    assert(owner && "validated native queue owner must be emitted");
    captures.push_back(owner);
    captureNames.push_back(builder.getStringAttr("queue_" + name));
  }
  auto process = acsim::ProcessOp::create(
      builder, placement.process->getLoc(), captures, placement.name,
      builder.getArrayAttr(captureNames), plan->pcs().front().name(),
      builder.getArrayAttr(pcs), builder.getArrayAttr(liveSlots),
      placement.fairnessCap, placement.specialization, plan->pcs().size());

  llvm::SmallVector<Block *> blocks(plan->blocks().size());
  for (const ProcessPcPlan &pc : plan->pcs()) {
    Region &state = process.getStates()[pc.id().value()];
    llvm::SmallVector<llvm::SmallVector<ProcessBlockId>> successors(
        plan->blocks().size());
    llvm::SmallVector<unsigned> indegree(plan->blocks().size(), 0);
    for (ProcessBlockId id : pc.blocks()) {
      const ProcessControlEdgePlan &edge = plan->blocks()[id.value()].edge();
      auto addSuccessor = [&](ProcessBlockId successor) {
        successors[id.value()].push_back(successor);
        ++indegree[successor.value()];
      };
      if (edge.kind() == ProcessControlEdgeKind::Branch) {
        addSuccessor(edge.trueBlock());
        addSuccessor(edge.falseBlock());
      } else if (edge.kind() == ProcessControlEdgeKind::LocalContinue) {
        addSuccessor(edge.targetBlock());
      }
    }
    std::set<unsigned> ready;
    for (ProcessBlockId id : pc.blocks())
      if (indegree[id.value()] == 0)
        ready.insert(id.value());
    llvm::SmallVector<unsigned> blockOrder;
    while (!ready.empty()) {
      unsigned id = *ready.begin();
      ready.erase(ready.begin());
      blockOrder.push_back(id);
      for (ProcessBlockId successor : successors[id])
        if (--indegree[successor.value()] == 0)
          ready.insert(successor.value());
    }
    assert(blockOrder.size() == pc.blocks().size() &&
           "validated intra-PC graph must be acyclic");
    for (unsigned id : blockOrder) {
      Block *block = new Block();
      state.push_back(block);
      blocks[id] = block;
    }
    Block *entry = blocks[pc.blocks().front().value()];
    for (Value capture : captures)
      entry->addArgument(capture.getType(), placement.process->getLoc());
  }

  llvm::SmallVector<std::set<std::string>> localDefinitions(
      plan->blocks().size());
  llvm::SmallVector<std::set<std::string>> neededValues(plan->blocks().size());
  llvm::StringMap<ProcessPlannedValue> valueRepresentatives;
  auto recordValue = [&](const ProcessPlannedValue &value) {
    valueRepresentatives.try_emplace(plannedValueKey(value), value);
  };
  auto recordUse = [&](ProcessBlockId block, const ProcessPlannedValue &value) {
    recordValue(value);
    if (value.kind() != ProcessPlannedValueKind::Capture)
      neededValues[block.value()].insert(plannedValueKey(value));
  };
  for (const ProcessBlockPlan &blockPlan : plan->blocks()) {
    auto &definitions = localDefinitions[blockPlan.id().value()];
    for (const ProcessTransitionLoadPlan &load : blockPlan.loads())
      for (const ProcessPlannedValue &replacement : load.replacements()) {
        recordValue(replacement);
        definitions.insert(plannedValueKey(replacement));
      }
    for (const ProcessActionPlan &action : blockPlan.actions()) {
      for (const ProcessPlannedValue &operand : action.operands())
        recordUse(blockPlan.id(), operand);
      for (const ProcessPlannedValue &result : action.results()) {
        recordValue(result);
        definitions.insert(plannedValueKey(result));
      }
    }
    const ProcessControlEdgePlan &edge = blockPlan.edge();
    if (edge.kind() == ProcessControlEdgeKind::Branch)
      recordUse(blockPlan.id(), edge.condition());
    if (edge.kind() == ProcessControlEdgeKind::Suspend)
      for (const ProcessTransitionStorePlan &store :
           plan->transitions()[edge.transition().value()].stores())
        recordUse(blockPlan.id(), store.source());
    for (const std::string &definition : definitions)
      neededValues[blockPlan.id().value()].erase(definition);
  }
  bool changed = true;
  while (changed) {
    changed = false;
    for (const ProcessBlockPlan &blockPlan : llvm::reverse(plan->blocks())) {
      llvm::SmallVector<ProcessBlockId, 2> successors;
      const ProcessControlEdgePlan &edge = blockPlan.edge();
      if (edge.kind() == ProcessControlEdgeKind::Branch) {
        successors.push_back(edge.trueBlock());
        successors.push_back(edge.falseBlock());
      } else if (edge.kind() == ProcessControlEdgeKind::LocalContinue) {
        successors.push_back(edge.targetBlock());
      }
      for (ProcessBlockId successor : successors)
        for (const std::string &key : neededValues[successor.value()])
          if (!localDefinitions[blockPlan.id().value()].contains(key))
            changed |= neededValues[blockPlan.id().value()].insert(key).second;
    }
  }

  llvm::SmallVector<llvm::StringMap<Value>> blockArguments(
      plan->blocks().size());
  for (const ProcessPcPlan &pc : plan->pcs()) {
    ProcessBlockId entryId = pc.blocks().front();
    for (ProcessBlockId id : pc.blocks()) {
      if (id == entryId)
        continue;
      for (const std::string &key : neededValues[id.value()]) {
        auto representative = valueRepresentatives.find(key);
        assert(representative != valueRepresentatives.end());
        Value argument = blocks[id.value()]->addArgument(
            representative->second.type(), placement.process->getLoc());
        blockArguments[id.value()][key] = argument;
      }
    }
  }

  OpBuilder::InsertionGuard guard(builder);
  llvm::SmallVector<llvm::StringMap<Value>> valuesByBlock(
      plan->blocks().size());
  llvm::SmallVector<llvm::StringMap<Value>> queueArgumentsByPc(
      plan->pcs().size());
  for (const ProcessPcPlan &pc : plan->pcs()) {
    Block *entry = blocks[pc.blocks().front().value()];
    auto &entryValues = valuesByBlock[pc.blocks().front().value()];
    for (auto [capture, argument] : llvm::zip_equal(
             plan->captures(),
             entry->getArguments().take_front(plan->captures().size()))) {
      std::string key = std::to_string(static_cast<unsigned>(
                            ProcessPlannedValueKind::Capture)) +
                        ":" + std::to_string(capture.id().value());
      entryValues[key] = argument;
    }
    for (auto [queue, argument] : llvm::zip_equal(
             referencedQueues,
             entry->getArguments().drop_front(plan->captures().size())))
      queueArgumentsByPc[pc.id().value()][queue.second] = argument;
  }
  for (const ProcessBlockPlan &blockPlan : plan->blocks()) {
    Block *block = blocks[blockPlan.id().value()];
    builder.setInsertionPointToStart(block);
    auto &values = valuesByBlock[blockPlan.id().value()];
    for (const auto &argument : blockArguments[blockPlan.id().value()])
      values[argument.getKey()] = argument.getValue();
    const ProcessPcPlan &owningPc = plan->pcs()[blockPlan.pc().value()];
    Block *pcEntry = blocks[owningPc.blocks().front().value()];
    for (auto [capture, argument] : llvm::zip_equal(
             plan->captures(),
             pcEntry->getArguments().take_front(plan->captures().size()))) {
      std::string key = std::to_string(static_cast<unsigned>(
                            ProcessPlannedValueKind::Capture)) +
                        ":" + std::to_string(capture.id().value());
      values[key] = argument;
    }

    for (const ProcessTransitionLoadPlan &load : blockPlan.loads()) {
      const ProcessLiveSlotPlan &slot = plan->liveSlots()[load.slot().value()];
      llvm::StringRef valueIdentity =
          valueTypeIdentities[slot.storageType().value()];
      auto storedType = acsim::ValueType::get(
          context, FlatSymbolRefAttr::get(
                       context, typeSymbols.symbolFor(valueIdentity)));
      auto loaded =
          acsim::LiveLoadOp::create(builder, placement.process->getLoc(),
                                    storedType, placement.name, slot.name());
      for (const ProcessPlannedValue &planned : load.replacements())
        values[plannedValueKey(planned)] = loaded.getResult();
    }

    llvm::StringSet<> requiredValues;
    const ProcessControlEdgePlan &edge = blockPlan.edge();
    if (edge.kind() == ProcessControlEdgeKind::Branch)
      requiredValues.insert(plannedValueKey(edge.condition()));
    if (edge.kind() == ProcessControlEdgeKind::Suspend) {
      const ProcessTransitionPlan &transition =
          plan->transitions()[edge.transition().value()];
      for (const ProcessTransitionStorePlan &store : transition.stores())
        requiredValues.insert(plannedValueKey(store.source()));
    }
    for (const ProcessActionPlan &action : blockPlan.actions())
      if (action.emission() != ProcessEmissionClass::ForwardOnly)
        for (const ProcessPlannedValue &operand : action.operands())
          requiredValues.insert(plannedValueKey(operand));

    for (const ProcessActionPlan &action : blockPlan.actions()) {
      if (isa_and_nonnull<ac::WaitUntilOp, ac::WaitForOp, ac::AwaitEventOp,
                          ac::AwaitQueueOp, ac::YieldSimOp>(
              action.sourceOperation()))
        continue;
      bool resultRequired =
          action.emission() != ProcessEmissionClass::ForwardOnly;
      for (const ProcessPlannedValue &result : action.results())
        resultRequired |= requiredValues.contains(plannedValueKey(result));
      if (!resultRequired) {
        if (action.kind() == ProcessActionKind::ForInitialize &&
            action.operands().size() == action.results().size())
          for (auto [result, operand] :
               llvm::zip_equal(action.results(), action.operands()))
            if (auto found = values.find(plannedValueKey(operand));
                found != values.end())
              values[plannedValueKey(result)] = found->second;
        continue;
      }

      llvm::SmallVector<Value> operands;
      bool operandsComplete = true;
      for (const ProcessPlannedValue &operand : action.operands()) {
        auto found = values.find(plannedValueKey(operand));
        if (found == values.end()) {
          operandsComplete = false;
          break;
        }
        operands.push_back(found->second);
      }
      if (!operandsComplete)
        continue;

      llvm::SmallVector<Value> results;
      if (action.kind() == ProcessActionKind::Constant) {
        int64_t value = static_cast<int64_t>(
            action.occurrence().syntheticConstant().constant());
        results.push_back(index::ConstantOp::create(
            builder, placement.process->getLoc(), value));
      } else if (action.emission() == ProcessEmissionClass::Inline ||
                 action.emission() == ProcessEmissionClass::Wrap ||
                 action.emission() == ProcessEmissionClass::Unwrap) {
        llvm::StringRef identity =
            generatedCalleeIdentities[action.callee()->value()];
        Type resultType = action.resultTypes().front();
        if (action.emission() == ProcessEmissionClass::Wrap) {
          ProcessLiveSlotId slot =
              action.occurrence().syntheticWrapper().slot();
          llvm::StringRef valueIdentity = valueTypeIdentities
              [plan->liveSlots()[slot.value()].storageType().value()];
          resultType = acsim::ValueType::get(
              context, FlatSymbolRefAttr::get(
                           context, typeSymbols.symbolFor(valueIdentity)));
        }
        results.push_back(
            acsim::InlineOp::create(
                builder, placement.process->getLoc(), resultType, operands,
                FlatSymbolRefAttr::get(context,
                                       typeSymbols.symbolFor(identity)))
                .getResult());
      } else if (action.emission() == ProcessEmissionClass::Invoke) {
        llvm::StringRef identity =
            generatedCalleeIdentities[action.callee()->value()];
        if (auto transfer =
                dyn_cast_or_null<ac::TryTransferOp>(action.sourceOperation())) {
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              transfer.getDestination()));
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              transfer.getSource()));
        } else if (auto send = dyn_cast_or_null<ac::TrySendOp>(
                       action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              send.getQueue()));
        else if (auto recv =
                     dyn_cast_or_null<ac::TryRecvOp>(action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              recv.getQueue()));
        else if (auto peek =
                     dyn_cast_or_null<ac::PeekOp>(action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              peek.getQueue()));
        else if (auto space =
                     dyn_cast_or_null<ac::SpaceOp>(action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              space.getQueue()));
        else if (auto schedule =
                     dyn_cast_or_null<ac::ScheduleOp>(action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              schedule.getTarget()));
        else if (auto recv =
                     dyn_cast_or_null<ac::TryEventOp>(action.sourceOperation()))
          operands.insert(operands.begin(),
                          queueArgumentsByPc[blockPlan.pc().value()].lookup(
                              recv.getEventQueue()));
        llvm::SmallVector<Type> invokeResultTypes;
        bool isNativeQueueRead =
            isa_and_nonnull<ac::TryRecvOp, ac::PeekOp, ac::TryEventOp>(
                action.sourceOperation());
        for (Type resultType : action.resultTypes()) {
          auto packetIdentity = nativePacketValueIdentities.find(resultType);
          if (!isNativeQueueRead ||
              packetIdentity == nativePacketValueIdentities.end()) {
            invokeResultTypes.push_back(resultType);
            continue;
          }
          invokeResultTypes.push_back(acsim::ValueType::get(
              context,
              FlatSymbolRefAttr::get(
                  context, typeSymbols.symbolFor(packetIdentity->second))));
        }
        auto invoke = acsim::InvokeOp::create(
            builder, placement.process->getLoc(), invokeResultTypes, operands,
            FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(identity)));
        results.append(invoke.getResults().begin(), invoke.getResults().end());
      } else {
        llvm::StringRef operationName =
            action.scalarOp()
                ? action.scalarOp()->name()
                : action.sourceOperation()->getName().getStringRef();
        OperationState state(placement.process->getLoc(), operationName);
        state.addOperands(operands);
        state.addTypes(action.resultTypes());
        if (action.sourceOperation())
          state.addAttributes(action.sourceOperation()->getAttrs());
        else if (action.scalarOp())
          for (const ProcessScalarAttribute &attribute :
               action.scalarOp()->attributes())
            if (attribute.name() == "predicate")
              state.addAttribute("predicate", builder.getI64IntegerAttr(2));
        Operation *emitted = builder.create(state);
        results.append(emitted->getResults().begin(),
                       emitted->getResults().end());
      }
      for (auto [planned, result] : llvm::zip_equal(action.results(), results))
        values[plannedValueKey(planned)] = result;
    }

    if (edge.kind() == ProcessControlEdgeKind::Branch) {
      auto condition = values.find(plannedValueKey(edge.condition()));
      assert(condition != values.end() &&
             "validated branch condition must be emitted");
      auto successorOperands = [&](ProcessBlockId target) {
        llvm::SmallVector<Value> operands;
        for (const std::string &key : neededValues[target.value()]) {
          auto found = values.find(key);
          assert(found != values.end() &&
                 "validated successor value must reach branch");
          operands.push_back(found->second);
        }
        return operands;
      };
      llvm::SmallVector<Value> trueOperands =
          successorOperands(edge.trueBlock());
      llvm::SmallVector<Value> falseOperands =
          successorOperands(edge.falseBlock());
      cf::CondBranchOp::create(
          builder, placement.process->getLoc(), condition->second,
          blocks[edge.trueBlock().value()], trueOperands,
          blocks[edge.falseBlock().value()], falseOperands);
      continue;
    }
    if (edge.kind() == ProcessControlEdgeKind::LocalContinue) {
      llvm::SmallVector<Value> operands;
      for (const std::string &key : neededValues[edge.targetBlock().value()]) {
        auto found = values.find(key);
        assert(found != values.end() &&
               "validated successor value must reach branch");
        operands.push_back(found->second);
      }
      cf::BranchOp::create(builder, placement.process->getLoc(),
                           blocks[edge.targetBlock().value()], operands);
      continue;
    }
    if (edge.kind() == ProcessControlEdgeKind::Terminate) {
      acsim::TerminateOp::create(
          builder, placement.process->getLoc(),
          edge.status() == ProcessTerminateStatus::Success ? "success"
                                                           : "failure");
      continue;
    }

    const ProcessTransitionPlan &transition =
        plan->transitions()[edge.transition().value()];
    for (const ProcessTransitionStorePlan &store : transition.stores()) {
      const ProcessLiveSlotPlan &slot = plan->liveSlots()[store.slot().value()];
      auto source = values.find(plannedValueKey(store.source()));
      assert(source != values.end() &&
             "validated live store source must be emitted");
      Value stored = source->second;
      llvm::StringRef valueIdentity =
          valueTypeIdentities[slot.storageType().value()];
      auto storedType = acsim::ValueType::get(
          context, FlatSymbolRefAttr::get(
                       context, typeSymbols.symbolFor(valueIdentity)));
      assert(stored.getType() == storedType &&
             "validated scalar wrapper must produce the live storage type");
      acsim::LiveStoreOp::create(builder, placement.process->getLoc(), stored,
                                 placement.name, slot.name());
    }
    const ProcessWakePlan &wakePlan = plan->wakes()[transition.wake().value()];
    llvm::StringRef typeIdentity = wakePlan.typeKey();
    typeIdentity.consume_front("@");
    auto wakeType = acsim::WakeType::get(
        context,
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(typeIdentity)));
    llvm::StringRef calleeIdentity =
        generatedCalleeIdentities[wakePlan.callee().value()];
    llvm::SmallVector<Value> wakeInputs;
    if (wakePlan.kind() == ProcessWakeKind::QueueReadable ||
        wakePlan.kind() == ProcessWakeKind::QueueWritable ||
        wakePlan.kind() == ProcessWakeKind::EventQueue)
      wakeInputs.push_back(
          queueArgumentsByPc[blockPlan.pc().value()].lookup(wakePlan.target()));
    auto wake = acsim::InvokeOp::create(
        builder, placement.process->getLoc(), TypeRange{wakeType}, wakeInputs,
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(calleeIdentity)));
    acsim::SuspendOp::create(
        builder, placement.process->getLoc(), wake.getResults().front(),
        FlatSymbolRefAttr::get(
            context, plan->pcs()[transition.targetPc().value()].name()));
  }
}

void ACIRToACSimPass::emitModuleBody(OpBuilder &builder,
                                     const ModulePlan &planned) {
  MLIRContext *context = builder.getContext();
  llvm::SmallVector<Attribute> portRecords;
  llvm::SmallVector<Attribute> resultRecords;
  llvm::SmallVector<Attribute> exports;
  auto reference = [&](llvm::StringRef identity) {
    return FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(identity));
  };
  for (const ModulePortPlan &port : planned.ports) {
    const bindings::PortBinding &metadata = port.metadata;
    portRecords.push_back(builder.getDictionaryAttr(
        {builder.getNamedAttr("accessor", reference(metadata.accessor)),
         builder.getNamedAttr("cardinality",
                              builder.getStringAttr(metadata.cardinality)),
         builder.getNamedAttr("delegation",
                              builder.getStringAttr(metadata.delegation)),
         builder.getNamedAttr("direction",
                              builder.getStringAttr(metadata.direction)),
         builder.getNamedAttr("interface", reference(metadata.interface)),
         builder.getNamedAttr("name", builder.getStringAttr(port.name)),
         builder.getNamedAttr("ownership",
                              builder.getStringAttr(metadata.ownership)),
         builder.getNamedAttr("payload", reference(metadata.payload)),
         builder.getNamedAttr("protocol", reference(metadata.protocol)),
         builder.getNamedAttr("role", reference(metadata.role)),
         builder.getNamedAttr("time_domain", reference(metadata.timeDomain))}));
    exports.push_back(FlatSymbolRefAttr::get(context, port.name));
  }
  for (const ModuleResultPlan &result : planned.results) {
    resultRecords.push_back(builder.getDictionaryAttr(
        {builder.getNamedAttr(
             "cpp_type", FlatSymbolRefAttr::get(
                             context, typeSymbols.symbolFor(result.cppType))),
         builder.getNamedAttr("name", builder.getStringAttr(result.name))}));
    exports.push_back(FlatSymbolRefAttr::get(context, result.name));
  }
  DictionaryAttr interface = builder.getDictionaryAttr(
      {builder.getNamedAttr("ports", builder.getArrayAttr(portRecords)),
       builder.getNamedAttr("resources", builder.getArrayAttr({})),
       builder.getNamedAttr("results", builder.getArrayAttr(resultRecords))});
  auto module = acsim::ModuleOp::create(
      builder, planned.source->getLoc(), builder.getStringAttr(planned.name),
      interface, planned.staticParams,
      builder.getStringAttr(planned.specialization),
      builder.getArrayAttr(exports));
  Block *body = new Block();
  module.getBody().push_back(body);
  OpBuilder::InsertionGuard guard(builder);
  builder.setInsertionPointToStart(body);
  llvm::DenseMap<Value, Value> emittedValues;
  llvm::SmallVector<Value> owners(planned.placements.size());
  llvm::StringMap<Value> queueOwners;
  llvm::SmallVector<llvm::SmallVector<Value, 2>> inputProjections(
      planned.placements.size());

  // Rank 0: owned placements.
  for (auto [placementIndex, placement] : llvm::enumerate(planned.placements)) {
    switch (placement.kind) {
    case PlacementPlan::Kind::Instance: {
      auto target = SymbolRefAttr::get(context, placement.targetSymbol);
      auto ownerType = acsim::OwnerType::get(context, target);
      owners[placementIndex] =
          acsim::InstanceOp::create(
              builder, planned.source->getLoc(), ownerType,
              builder.getStringAttr(placement.name), target,
              placement.staticArgs,
              builder.getStringAttr(placement.specialization))
              .getResult();
      break;
    }
    case PlacementPlan::Kind::Array: {
      auto target = SymbolRefAttr::get(context, placement.targetSymbol);
      auto ownerType = acsim::OwnerType::get(context, target);
      auto shape = builder.getDenseI64ArrayAttr(placement.shape);
      auto arrayType = acsim::ArrayType::get(context, shape, ownerType);
      owners[placementIndex] =
          acsim::ArrayOp::create(
              builder, planned.source->getLoc(), arrayType,
              builder.getStringAttr(placement.name), target,
              placement.staticArgs,
              builder.getStringAttr(placement.specialization), shape)
              .getResult();
      break;
    }
    case PlacementPlan::Kind::RuntimeObject: {
      auto target = SymbolRefAttr::get(
          context, typeSymbols.symbolFor(placement.targetSymbol));
      auto ownerType = acsim::OwnerType::get(context, target);
      owners[placementIndex] =
          acsim::InstanceOp::create(
              builder, planned.source->getLoc(), ownerType,
              builder.getStringAttr(placement.name), target,
              placement.staticArgs,
              builder.getStringAttr(placement.specialization))
              .getResult();
      queueOwners[placement.name] = owners[placementIndex];
      break;
    }
    case PlacementPlan::Kind::Process:
      break;
    }
  }

  auto emitPort = [&](Value base, const PortEndpointPlan &endpoint) {
    const bindings::PortBinding &port = endpoint.metadata;
    auto type = acsim::PortType::get(
        context,
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(port.interface)),
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(port.role)),
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(port.payload)),
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(port.protocol)));
    return acsim::PortOp::create(
               builder, planned.source->getLoc(), type, base,
               FlatSymbolRefAttr::get(context,
                                      typeSymbols.symbolFor(port.accessor)))
        .getResult();
  };

  // Rank 2: exact typed endpoint projections.
  for (auto [placementIndex, placement] : llvm::enumerate(planned.placements)) {
    if (!owners[placementIndex])
      continue;
    for (const PortEndpointPlan &endpoint : placement.outputPorts)
      emittedValues[endpoint.value] =
          emitPort(owners[placementIndex], endpoint);
    for (const PortEndpointPlan &endpoint : placement.inputPorts)
      inputProjections[placementIndex].push_back(
          emitPort(owners[placementIndex], endpoint));
  }

  // Native Flow module boundaries are also exact endpoint projections.  Emit
  // all of them in rank 2, before any rank-3 binds.  Delaying these projections
  // until the rank-6 export loop made modules with native Flow boundaries
  // non-canonical whenever they also contained a construction-time bind.
  for (const ModulePortPlan &port : planned.ports) {
    if (!port.nativeFlow)
      continue;
    Value queue = queueOwners.lookup(port.queue);
    assert(queue && "validated native Flow queue owner must be emitted");
    bindings::PortBinding local = port.metadata;
    local.accessor = port.localAccessor;
    emittedValues[port.source] =
        emitPort(queue, PortEndpointPlan{port.source, local, true});
  }

  // Pure Flow relay modules forward identity in SSA and therefore project no
  // endpoint and create no runtime link.
  bool aliasProgress = true;
  while (aliasProgress) {
    aliasProgress = false;
    for (const PlacementPlan &placement : planned.placements)
      for (auto [result, source] : placement.flowAliases)
        if (!emittedValues.count(result))
          if (Value resolved = emittedValues.lookup(source)) {
            emittedValues[result] = resolved;
            aliasProgress = true;
          }
  }

  // Rank 3: ACIR SSA endpoint uses become exact construction-time binds.
  for (auto [placementIndex, placement] : llvm::enumerate(planned.placements))
    for (auto [inputIndex, endpoint] : llvm::enumerate(placement.inputPorts)) {
      Value source = emittedValues.lookup(endpoint.value);
      assert(source && "validated endpoint producer must be projected");
      acsim::BindOp::create(
          builder, planned.source->getLoc(), source,
          inputProjections[placementIndex][inputIndex],
          builder.getStringAttr(endpoint.nativeFlow ? "flow" : "port"));
    }

  // Rank 4: pure binding calls. Static constructor arguments specialize the
  // binding and therefore do not become dynamic acsim.inline operands.
  for (const PureCallPlan &call : planned.pureCalls) {
    auto resultType = acsim::ExprType::get(
        context,
        FlatSymbolRefAttr::get(context, typeSymbols.symbolFor(call.cppType)));
    auto inlineOp = acsim::InlineOp::create(
        builder, call.source->getLoc(), resultType, ValueRange{},
        FlatSymbolRefAttr::get(context, call.binding));
    emittedValues[call.result] = inlineOp.getResult();
  }

  // Rank 6: ordered endpoint and scalar exports.
  llvm::SmallVector<Value> returned;
  for (const ModulePortPlan &port : planned.ports) {
    Value value = emittedValues.lookup(port.source);
    assert(value && "validated module port producer must be emitted");
    auto exportOp = acsim::ExportOp::create(
        builder, planned.source->getLoc(), value.getType(), value,
        builder.getStringAttr(port.name), reference(port.metadata.role));
    returned.push_back(exportOp.getResult());
  }
  llvm::StringRef resultRole = typeSymbols.symbolFor(kResultRoleIdentity);
  for (const ModuleResultPlan &result : planned.results) {
    Value value = emittedValues.lookup(result.source);
    assert(value && "validated module result producer must be emitted");
    auto exportOp = acsim::ExportOp::create(
        builder, planned.source->getLoc(), value.getType(), value,
        builder.getStringAttr(result.name),
        FlatSymbolRefAttr::get(context, resultRole));
    returned.push_back(exportOp.getResult());
  }

  // Rank 8: stateful processes.
  for (const PlacementPlan &placement : planned.placements)
    if (placement.kind == PlacementPlan::Kind::Process)
      emitProcessBody(builder, placement, emittedValues, queueOwners);

  acsim::ReturnOp::create(builder, planned.source->getLoc(), returned);
}

mlir::FailureOr<mlir::OwningOpRef<mlir::ModuleOp>>
ACIRToACSimPass::emit(mlir::ModuleOp input) {
  MLIRContext *context = input.getContext();
  mlir::OwningOpRef<mlir::ModuleOp> staged =
      mlir::ModuleOp::create(input.getLoc());
  (*staged)->setAttr("ac.contract_epoch", input->getAttr("ac.contract_epoch"));
  OpBuilder builder(context);
  builder.setInsertionPointToEnd(staged->getBody());

  llvm::SmallVector<Attribute> construction;
  llvm::SmallVector<Attribute> destructionAttrs;
  for (const std::string &path : constructionOrder)
    construction.push_back(builder.getStringAttr(path));
  for (auto it = constructionOrder.rbegin(); it != constructionOrder.rend();
       ++it)
    destructionAttrs.push_back(builder.getStringAttr(*it));

  DictionaryAttr fingerprints = builder.getDictionaryAttr(
      {builder.getNamedAttr("frozen_acir",
                            builder.getStringAttr(frozenAcirFingerprint)),
       builder.getNamedAttr("binding_lock",
                            builder.getStringAttr(bindingLockFingerprint)),
       builder.getNamedAttr("provider",
                            builder.getStringAttr(providerFingerprint)),
       builder.getNamedAttr("profile",
                            builder.getStringAttr(profileFingerprint)),
       builder.getNamedAttr("toolchain",
                            builder.getStringAttr(toolchainFingerprint)),
       builder.getNamedAttr("schema_set",
                            builder.getStringAttr(schemaSetFingerprint))});

  auto model = acsim::ModelOp::create(
      builder, input.getLoc(),
      builder.getStringAttr(selectedSystem.getSymName()),
      builder.getStringAttr(kEpoch),
      FlatSymbolRefAttr::get(context, selectedSystem.getRoot()),
      builder.getArrayAttr(construction),
      builder.getArrayAttr(destructionAttrs), fingerprints);

  Block *modelBody = new Block();
  model.getBody().push_back(modelBody);
  builder.setInsertionPointToStart(modelBody);

  // Rank 0: acsim.type declarations, strictly symbol-sorted.
  for (const TypeDeclaration *declaration : typeSymbols.declarations()) {
    IntegerAttr period;
    IntegerAttr phase;
    IntegerAttr tickScale;
    FlatSymbolRefAttr parent;
    DictionaryAttr bridge;
    if (declaration->period) {
      period = builder.getI64IntegerAttr(*declaration->period);
      phase = builder.getI64IntegerAttr(declaration->phase);
      tickScale = builder.getI64IntegerAttr(declaration->tickScale);
    }
    if (declaration->parent)
      parent = FlatSymbolRefAttr::get(
          context, typeSymbols.symbolFor(*declaration->parent));
    if (declaration->bridgeKind)
      bridge = builder.getDictionaryAttr(
          {builder.getNamedAttr(
               "kind", builder.getStringAttr(*declaration->bridgeKind)),
           builder.getNamedAttr(
               "owner",
               FlatSymbolRefAttr::get(context, *declaration->bridgeOwner))});
    acsim::TypeOp::create(builder, input.getLoc(),
                          builder.getStringAttr(declaration->symbol),
                          builder.getStringAttr(declaration->cpp),
                          builder.getStringAttr(declaration->kind),
                          builder.getStringAttr(declaration->fingerprint),
                          period, phase, tickScale, parent, bridge);
  }

  // Rank 1: acsim.binding records, strictly symbol-sorted.
  {
    llvm::SmallVector<const bindings::BindingRecord *> records;
    for (const bindings::ResolvedBinding &selection : resolution->selections())
      records.push_back(&selection.record());
    llvm::sort(records, [](const bindings::BindingRecord *left,
                           const bindings::BindingRecord *right) {
      return left->binding() < right->binding();
    });
    for (const bindings::BindingRecord *record : records)
      acsim::BindingOp::create(builder, input.getLoc(),
                               builder.getStringAttr(record->binding()),
                               cast<DictionaryAttr>(convertBindingRecord(
                                   builder, *record, typeSymbols)));
  }

  // Rank 2: acsim.module declarations, child-before-parent with
  // symbol-sorted ties between independent nodes.
  for (const ModulePlan &planned : modules)
    emitModuleBody(builder, planned);

  // Rank 3: one typed dispatch row per runtime object, dense IDs.
  llvm::SmallVector<acsim::DispatchOp> dispatches;
  for (auto [id, row] : llvm::enumerate(runtimeRows)) {
    const ModulePlan &module = modules[row.moduleIndex];
    const PlacementPlan &placement = module.placements[row.placementIndex];
    auto target =
        SymbolRefAttr::get(context, module.name,
                           {FlatSymbolRefAttr::get(context, placement.name)});
    std::string work = placement.work;
    std::string xfer = placement.xfer;
    std::string reset = placement.reset;
    std::string validate = placement.validate;
    if (placement.kind == PlacementPlan::Kind::Process) {
      std::string base =
          ("acsim_generated::" + module.name + "::s" +
           module.specialization.substr(7) + "::" + placement.name + "::p" +
           placement.specialization.substr(7) + "::");
      work = base + "work";
      xfer = base + "xfer";
      reset = base + "reset";
      validate = base + "validate";
    }
    dispatches.push_back(acsim::DispatchOp::create(
        builder, input.getLoc(), acsim::ObjectIdType::get(context),
        acsim::ActivationIdType::get(context), target,
        builder.getStringAttr(row.path),
        builder.getDenseI64ArrayAttr(row.indices),
        builder.getI64IntegerAttr(static_cast<int64_t>(id)),
        builder.getI64IntegerAttr(static_cast<int64_t>(id)),
        builder.getStringAttr(work), builder.getStringAttr(xfer),
        builder.getStringAttr(reset), builder.getStringAttr(validate)));
  }

  // Rank 4: static activation adjacency. Ordinary runtime objects have their
  // self wake. Timed event queues instead have only arrival edges to their
  // consumer; their proposals join Xfer through explicit commit registration.
  std::set<std::pair<unsigned, unsigned>> activationEdges;
  for (auto [id, row] : llvm::enumerate(runtimeRows))
    if (!modules[row.moduleIndex].placements[row.placementIndex].eventQueue)
      activationEdges.emplace(id, id);
  for (auto [moduleIndex, module] : llvm::enumerate(modules))
    for (const BindingEdgePlan &edge : module.bindingEdges) {
      if (!edge.activates)
        continue;
      for (auto [sourceId, source] : llvm::enumerate(runtimeRows)) {
        if (edge.nativeFlow) {
          const PlacementPlan &sourcePlacement =
              module.placements[edge.sourcePlacement];
          const PlacementPlan &targetPlacement =
              module.placements[edge.targetPlacement];
          std::string sourceSuffix =
              "." + sourcePlacement.name + "." + edge.sourceChild;
          if (!StringRef(source.path).ends_with(sourceSuffix))
            continue;
          for (auto [targetId, target] : llvm::enumerate(runtimeRows)) {
            std::string targetSuffix =
                "." + targetPlacement.name + "." + edge.targetChild;
            if (!StringRef(target.path).ends_with(targetSuffix))
              continue;
            for (auto [linkId, link] : llvm::enumerate(runtimeRows)) {
              if (link.moduleIndex != moduleIndex ||
                  link.placementIndex != edge.linkPlacement)
                continue;
              std::string sourcePath = link.contextPath + sourceSuffix;
              std::string targetPath = link.contextPath + targetSuffix;
              if (source.path != sourcePath || target.path != targetPath)
                continue;
              activationEdges.emplace(sourceId, linkId);
              activationEdges.emplace(targetId, linkId);
              activationEdges.emplace(linkId, sourceId);
              activationEdges.emplace(linkId, targetId);
            }
          }
          continue;
        }
        if (source.moduleIndex != moduleIndex ||
            source.placementIndex != edge.sourcePlacement)
          continue;
        for (auto [targetId, target] : llvm::enumerate(runtimeRows))
          if (target.moduleIndex == moduleIndex &&
              target.placementIndex == edge.targetPlacement &&
              target.contextPath == source.contextPath)
            activationEdges.emplace(sourceId, targetId);
      }
    }
  for (auto [source, target] : activationEdges)
    acsim::ActivateOp::create(builder, input.getLoc(),
                              dispatches[source].getActivation(),
                              dispatches[target].getObject());

  if (failed(mlir::verify(*staged)) ||
      failed(acsim::verifyCanonicalACSimFile(*staged)))
    return mlir::failure();
  return staged;
}

void ACIRToACSimPass::publish(mlir::ModuleOp input, mlir::ModuleOp staged) {
  Operation *model = &staged.getBody()->front();
  model->remove();

  llvm::SmallVector<Operation *> obsolete;
  for (Operation &operation : *input.getBody())
    obsolete.push_back(&operation);
  for (Operation *operation : obsolete)
    operation->erase();
  input.getBody()->push_back(model);

  llvm::SmallVector<NamedAttribute> retained;
  for (NamedAttribute attribute : input->getAttrs())
    if (attribute.getName() == "ac.contract_epoch")
      retained.push_back(attribute);
  input->setAttrs(retained);
}

mlir::LogicalResult ACIRToACSimPass::lower(mlir::ModuleOp input) {
  std::string frozenText;
  {
    llvm::raw_string_ostream output(frozenText);
    input.print(output);
  }
  mlir::OwningOpRef<mlir::ModuleOp> lowered(
      cast<mlir::ModuleOp>(input->clone()));
  if (failed(plan(*lowered)))
    return mlir::failure();
  // The model fingerprint names the exact frozen ACIR input, not the private
  // combinational clone used during conversion.
  frozenAcirFingerprint = bindings::sha256Fingerprint(frozenText);
  auto staged = emit(*lowered);
  if (failed(staged))
    return mlir::failure();
  publish(input, **staged);
  return mlir::success();
}

mlir::LogicalResult ACIRToACSimPass::lowerArbiters(mlir::ModuleOp input) {
  llvm::SmallVector<ac::ArbitrateOp> arbiters;
  input.walk([&](ac::ArbitrateOp arbiter) { arbiters.push_back(arbiter); });
  for (ac::ArbitrateOp arbiter : arbiters) {
    if (failed(arbiter.verify()))
      return mlir::failure();
    OpBuilder builder(arbiter);
    llvm::StringMap<unsigned> resourceIds;
    llvm::SmallVector<Value> occupied;
    auto resourceId = [&](Attribute resource) {
      StringRef name = cast<FlatSymbolRefAttr>(resource).getValue();
      auto [entry, inserted] =
          resourceIds.try_emplace(name, resourceIds.size());
      if (inserted)
        occupied.push_back(Value());
      return entry->second;
    };
    llvm::SmallVector<Value> grants;
    Value trueValue;
    for (auto [request, candidate] :
         llvm::zip(arbiter.getRequests(), arbiter.getCandidateResources())) {
      auto resources = cast<ArrayAttr>(candidate);
      llvm::SmallVector<Value> blockers;
      llvm::SmallDenseSet<Value, 4> seenBlockers;
      blockers.reserve(resources.size());
      for (Attribute resource : resources)
        if (Value prior = occupied[resourceId(resource)];
            prior && seenBlockers.insert(prior).second)
          blockers.push_back(prior);

      Value grant = request;
      if (!blockers.empty()) {
        Value blocked = blockers.front();
        for (Value blocker : llvm::drop_begin(blockers))
          blocked =
              arith::OrIOp::create(builder, arbiter.getLoc(), blocked, blocker);
        if (!trueValue)
          trueValue = arith::ConstantOp::create(builder, arbiter.getLoc(),
                                                builder.getI1Type(),
                                                builder.getBoolAttr(true));
        Value available = arith::XOrIOp::create(builder, arbiter.getLoc(),
                                                blocked, trueValue);
        grant = arith::AndIOp::create(builder, arbiter.getLoc(), request,
                                      available);
      }
      grants.push_back(grant);
      for (Attribute resource : resources) {
        Value &slot = occupied[resourceId(resource)];
        Value prior = slot;
        slot = prior ? arith::OrIOp::create(builder, arbiter.getLoc(), prior,
                                            grant)
                     : grant;
      }
    }
    if (grants.size() != arbiter.getNumResults())
      return arbiter.emitOpError(
          "cannot lower mismatched candidate and grant counts");
    arbiter->replaceAllUsesWith(grants);
    arbiter.erase();
  }
  return mlir::success();
}

} // namespace

std::unique_ptr<mlir::Pass>
createACIRToACSimPass(ACIRToACSimPassOptions options) {
  return std::make_unique<ACIRToACSimPass>(std::move(options));
}

} // namespace acir
