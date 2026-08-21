#include "acir/CodeGen/Generator.h"

#include "ProcessGenerator.h"

#include "llvm/ADT/SmallVector.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/ADT/Twine.h"
#include "llvm/Support/FormatVariadic.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <set>
#include <sstream>
#include <system_error>

namespace acir::codegen {
namespace {

llvm::Error generatorError(const llvm::Twine &code,
                           const llvm::Twine &message) {
  return llvm::createStringError(
      std::make_error_code(std::errc::invalid_argument), code + ": " + message);
}

bool isIdentifier(llvm::StringRef value) {
  if (value.empty() ||
      !(std::isalpha(static_cast<unsigned char>(value.front())) ||
        value.front() == '_'))
    return false;
  return std::all_of(value.drop_front().begin(), value.end(), [](char value) {
    return std::isalnum(static_cast<unsigned char>(value)) || value == '_';
  });
}

bool isQualifiedName(llvm::StringRef value) {
  if (value.empty() || value.starts_with(':') || value.ends_with(':'))
    return false;
  while (!value.empty()) {
    auto split = value.split("::");
    if (!isIdentifier(split.first))
      return false;
    if (split.second.empty())
      return true;
    value = split.second;
  }
  return true;
}

bool isIncludePath(llvm::StringRef value) {
  return !value.empty() && !value.starts_with('/') && !value.contains('\\') &&
         !value.contains('"') && !value.contains("..") &&
         std::all_of(value.begin(), value.end(), [](char character) {
           return character >= 0x20 && character != 0x7f;
         });
}

bool isNormalizedRelativePath(llvm::StringRef value) {
  if (value.empty() || value.starts_with('/') || value.ends_with('/') ||
      value.contains('\\'))
    return false;
  while (!value.empty()) {
    auto [component, rest] = value.split('/');
    if (component.empty() || component == "." || component == "..")
      return false;
    value = rest;
  }
  return true;
}

const BindingPlan *findBinding(const ModelPlan &plan, llvm::StringRef symbol) {
  auto found = std::find_if(
      plan.bindings.begin(), plan.bindings.end(),
      [&](const BindingPlan &binding) { return binding.symbol == symbol; });
  return found == plan.bindings.end() ? nullptr : &*found;
}

const ModulePlan *findModule(const ModelPlan &plan, llvm::StringRef symbol) {
  auto found = std::find_if(
      plan.modules.begin(), plan.modules.end(),
      [&](const ModulePlan &module) { return module.symbol == symbol; });
  return found == plan.modules.end() ? nullptr : &*found;
}

const TypePlan *findType(const ModelPlan &plan, llvm::StringRef symbol) {
  auto found =
      std::find_if(plan.types.begin(), plan.types.end(),
                   [&](const TypePlan &type) { return type.symbol == symbol; });
  return found == plan.types.end() ? nullptr : &*found;
}

const ModulePlan *rootModule(const ModelPlan &plan) {
  return findModule(plan, plan.rootSymbol);
}

std::vector<const PlacementPlan *> rootHostInputs(const ModelPlan &plan) {
  std::vector<const PlacementPlan *> inputs;
  if (const ModulePlan *root = rootModule(plan))
    for (const PlacementPlan &placement : root->placements)
      if (!placement.hostInput.empty())
        inputs.push_back(&placement);
  std::sort(inputs.begin(), inputs.end(), [](const auto *left, const auto *right) {
    return left->hostInput < right->hostInput;
  });
  return inputs;
}

std::vector<const PlacementPlan *> rootHostOutputs(const ModelPlan &plan) {
  std::vector<const PlacementPlan *> outputs;
  if (const ModulePlan *root = rootModule(plan))
    for (const PlacementPlan &placement : root->placements)
      if (!placement.hostOutput.empty())
        outputs.push_back(&placement);
  std::sort(outputs.begin(), outputs.end(), [](const auto *left,
                                               const auto *right) {
    return left->hostOutput < right->hostOutput;
  });
  return outputs;
}

llvm::Expected<std::string> hostInputCppType(const ModelPlan &plan,
                                             const PlacementPlan &input) {
  const TypePlan *queue = findType(plan, input.target);
  if (!queue || queue->kind != TypeKind::RuntimeObject)
    return generatorError("ACLOWER-HOST-INPUT",
                          "host input does not target a runtime queue");
  llvm::StringRef spelling(queue->cppType);
  constexpr llvm::StringLiteral queueTemplatePrefix("gfsim::Queue<");
  bool envelopeMatches = spelling.consume_front(queueTemplatePrefix) &&
                         spelling.consume_back(">");
  if (!envelopeMatches)
    return generatorError("ACLOWER-HOST-INPUT",
                          "host input queue has no closed element type");
  return spelling.str();
}

llvm::Expected<std::string> cppLiteral(const llvm::json::Value &value) {
  if (value.kind() == llvm::json::Value::Null)
    return std::string("{}");
  if (auto boolean = value.getAsBoolean())
    return std::string(*boolean ? "true" : "false");
  if (auto integer = value.getAsInteger())
    return std::to_string(*integer);
  if (auto number = value.getAsNumber())
    return llvm::formatv("{0}", *number).str();
  if (value.getAsString())
    return llvm::formatv("{0}", value).str();
  if (const llvm::json::Array *array = value.getAsArray()) {
    std::string result = "{";
    for (auto [index, element] : llvm::enumerate(*array)) {
      auto literal = cppLiteral(element);
      if (!literal)
        return literal.takeError();
      if (index != 0)
        result.append(", ");
      result.append(*literal);
    }
    return result.append("}");
  }
  if (const llvm::json::Object *object = value.getAsObject()) {
    std::vector<std::pair<std::string, const llvm::json::Value *>> fields;
    for (const auto &field : *object)
      fields.emplace_back(field.first.str(), &field.second);
    std::sort(fields.begin(), fields.end());
    std::string result = "{";
    for (auto [index, field] : llvm::enumerate(fields)) {
      auto literal = cppLiteral(*field.second);
      if (!literal)
        return literal.takeError();
      if (index != 0)
        result.append(", ");
      result.append(*literal);
    }
    return result.append("}");
  }
  return generatorError("ACLOWER-PARAM-PHASE",
                        "static value cannot be represented in C++");
}

llvm::Expected<std::string> bindingType(const ModelPlan &plan,
                                        const BindingPlan &binding) {
  std::vector<const ParameterPlan *> templateArguments;
  for (const ParameterPlan &parameter : binding.parameters)
    if (parameter.mapping == ParameterMappingKind::TemplateArgument)
      templateArguments.push_back(&parameter);
  std::sort(templateArguments.begin(), templateArguments.end(),
            [](const ParameterPlan *left, const ParameterPlan *right) {
              return left->ordinal < right->ordinal;
            });
  if (templateArguments.empty())
    return binding.cppSymbol;
  std::string result = binding.cppSymbol + "<";
  for (auto [index, parameter] : llvm::enumerate(templateArguments)) {
    std::string argument;
    if (auto identity = parameter->canonicalValue.getAsString()) {
      const TypePlan *type = findType(plan, *identity);
      if (!type)
        type = findType(plan, parameter->cppType);
      if (!type)
        return generatorError(
            "ACLOWER-TYPE-MISMATCH",
            "template type identity has no concrete C++ realization");
      argument = type->cppType;
    } else {
      auto literal = cppLiteral(parameter->canonicalValue);
      if (!literal)
        return literal.takeError();
      argument = std::move(*literal);
    }
    if (index != 0)
      result.append(", ");
    result.append(argument);
  }
  return result.append(">");
}

llvm::Expected<std::string> constructorSuffix(const BindingPlan &binding) {
  std::string result;
  for (const llvm::json::Value &argument : binding.constructorArguments) {
    auto literal = cppLiteral(argument);
    if (!literal)
      return literal.takeError();
    result.append(", ").append(*literal);
  }
  return result;
}

constexpr llvm::StringLiteral kGeneratedFingerprintPlaceholder =
    "sha256:0000000000000000000000000000000000000000000000000000000000000000";

llvm::Expected<Fingerprint>
sourceBundleFingerprint(const std::vector<GeneratedFile> &files) {
  llvm::json::Array sources;
  for (const GeneratedFile &file : files)
    sources.push_back(llvm::json::Object{{"path", file.relativePath},
                                         {"content", file.content}});
  llvm::json::Object preimage{{"domain", "acsim-source-bundle-0.2"},
                              {"sources", std::move(sources)}};
  return fingerprintCanonicalJson(llvm::json::Value(std::move(preimage)));
}

llvm::Error embedSourceBundleFingerprint(SourceBundle &bundle) {
  auto fingerprint = sourceBundleFingerprint(bundle.files);
  if (!fingerprint)
    return fingerprint.takeError();
  size_t replacements = 0;
  for (GeneratedFile &file : bundle.files) {
    size_t position = file.content.find(kGeneratedFingerprintPlaceholder);
    if (position == std::string::npos)
      continue;
    if (file.content.find(kGeneratedFingerprintPlaceholder,
                          position + kGeneratedFingerprintPlaceholder.size()) !=
        std::string::npos)
      return generatorError("ACLOWER-FINGERPRINT",
                            "generated fingerprint placeholder is repeated");
    file.content.replace(position, kGeneratedFingerprintPlaceholder.size(),
                         *fingerprint);
    file.fingerprint = computeFingerprint(file.content);
    ++replacements;
  }
  if (replacements != 1)
    return generatorError("ACLOWER-FINGERPRINT",
                          "generated fingerprint placeholder is incomplete");
  bundle.buildFingerprint = std::move(*fingerprint);
  bundle.sourceFingerprint = bundle.buildFingerprint;
  return llvm::Error::success();
}

llvm::Expected<std::string> placementType(const ModelPlan &plan,
                                          const PlacementPlan &placement) {
  llvm::StringRef target = placement.target;
  std::string base;
  if (const BindingPlan *binding = findBinding(plan, target)) {
    auto type = bindingType(plan, *binding);
    if (!type)
      return type.takeError();
    base = std::move(*type);
  } else if (const ModulePlan *module = findModule(plan, target))
    base = module->className;
  else if (const TypePlan *type = findType(plan, target);
           type && type->kind == TypeKind::RuntimeObject)
    base = type->cppType;
  else
    return generatorError("ACLOWER-TYPE-MISMATCH",
                          "placement target has no typed realization");

  for (auto extent = placement.shape.rbegin(); extent != placement.shape.rend();
       ++extent) {
    std::string wrapped = "std::array<";
    wrapped.append(base)
        .append(", ")
        .append(std::to_string(*extent))
        .append(">");
    base = std::move(wrapped);
  }
  return base;
}

GeneratedFile makeFile(std::string path, std::string content) {
  GeneratedFile file{std::move(path), std::move(content), {}};
  file.fingerprint = computeFingerprint(file.content);
  return file;
}

llvm::Expected<std::string> moduleValueExpression(const ModelPlan &plan,
                                                  const ModulePlan &module,
                                                  llvm::StringRef value);

llvm::Expected<GeneratedFile> moduleHeader(const ModelPlan &plan,
                                           const ModulePlan &module) {
  std::set<std::string> headers;
  std::set<std::string> moduleHeaders;
  std::set<std::pair<std::string, std::string>> conceptChecks;
  bool hasRuntimeObject = false;
  for (const PlacementPlan &placement : module.placements) {
    llvm::StringRef target = placement.target;
    target = target.take_until([](char value) { return value == ':'; });
    if (const BindingPlan *binding = findBinding(plan, target)) {
      headers.insert(binding->header);
      auto type = bindingType(plan, *binding);
      if (!type)
        return type.takeError();
      conceptChecks.emplace(binding->conceptName, std::move(*type));
    } else if (const ModulePlan *nested = findModule(plan, target)) {
      moduleHeaders.insert("generated/modules/" + nested->className + ".h");
    } else if (const TypePlan *type = findType(plan, target);
               type && type->kind == TypeKind::RuntimeObject) {
      hasRuntimeObject = true;
    }
  }
  for (const ExpressionPlan &expression : module.expressions) {
    const BindingPlan *binding = findBinding(plan, expression.callee);
    if (!binding)
      continue;
    headers.insert(binding->header);
    auto type = bindingType(plan, *binding);
    if (!type)
      return type.takeError();
    conceptChecks.emplace(binding->conceptName, std::move(*type));
  }

  std::ostringstream output;
  output << "#pragma once\n\n#include \"gfsim/object.h\"\n";
  if (hasRuntimeObject)
    output << "#include \"gfsim/queue.h\"\n";
  if (std::any_of(module.placements.begin(), module.placements.end(),
                  [](const PlacementPlan &placement) {
                    return !placement.shape.empty();
                  }))
    output << "#include <array>\n";
  for (const std::string &header : headers)
    output << "#include \"" << header << "\"\n";
  for (const std::string &header : moduleHeaders)
    output << "#include \"" << header << "\"\n";
  for (const ProcessPlan &process : module.processes)
    output << "#include \"generated/processes/" << process.className
           << ".h\"\n";
  output << "\nnamespace acsim_generated {\n\n";
  for (const auto &[conceptName, type] : conceptChecks)
    output << "static_assert(" << conceptName << '<' << type << ">);\n";
  if (!conceptChecks.empty())
    output << '\n';
  output << "class " << module.className
         << " final : public gfsim::Module {\npublic:\n  " << module.className
         << "(std::string name, gfsim::ObjectId id, gfsim::SimObject "
            "*parent, gfsim::ObjectId &nextObjectId);\n";
  for (const ExportPlan &exported : module.exports) {
    if (llvm::StringRef(exported.resultType).starts_with("!acsim.port<")) {
      auto expression =
          moduleValueExpression(plan, module, exported.sourceValue);
      if (!expression)
        return expression.takeError();
      output << "  decltype(auto) " << exported.symbol << "() { return "
             << *expression << "; }\n"
             << "  decltype(auto) " << exported.symbol << "() const { return "
             << *expression << "; }\n";
    } else {
      output << "  decltype(auto) " << exported.symbol << "();\n"
             << "  decltype(auto) " << exported.symbol << "() const;\n";
    }
  }
  output
      << "\nprivate:\n  friend class Model;\n  friend struct DispatchAccess;\n";
  for (const PlacementPlan &placement : module.placements) {
    auto type = placementType(plan, placement);
    if (!type)
      return type.takeError();
    output << "  " << *type << ' ' << placement.memberName << ";\n";
  }
  for (const ProcessPlan &process : module.processes)
    output << "  " << process.className << ' ' << process.symbol << "_;\n";
  output << "};\n\n} // namespace acsim_generated\n";
  return makeFile("include/generated/modules/" + module.className + ".h",
                  output.str());
}

llvm::Expected<std::string> moduleValueExpression(const ModelPlan &plan,
                                                  const ModulePlan &module,
                                                  llvm::StringRef value) {
  auto placement =
      std::find_if(module.placements.begin(), module.placements.end(),
                   [&](const PlacementPlan &candidate) {
                     return candidate.resultValue == value;
                   });
  if (placement != module.placements.end())
    return placement->memberName;

  auto projection =
      std::find_if(module.projections.begin(), module.projections.end(),
                   [&](const ProjectionPlan &candidate) {
                     return candidate.resultValue == value;
                   });
  if (projection != module.projections.end()) {
    auto base = moduleValueExpression(plan, module, projection->baseValue);
    if (!base)
      return base.takeError();
    for (uint64_t index : projection->indices)
      base->append("[").append(std::to_string(index)).append("]");
    if (projection->kind != ProjectionKind::Element) {
      const TypePlan *accessor = findType(plan, projection->accessor);
      if (!accessor || !isIdentifier(accessor->cppType))
        return generatorError("ACLOWER-TYPE-MISMATCH",
                              "projection accessor has no safe C++ name");
      base->append(".").append(accessor->cppType).append("()");
    }
    return base;
  }

  auto expression =
      std::find_if(module.expressions.begin(), module.expressions.end(),
                   [&](const ExpressionPlan &candidate) {
                     return candidate.resultValue == value;
                   });
  if (expression != module.expressions.end()) {
    const BindingPlan *binding = findBinding(plan, expression->callee);
    if (!binding || binding->effect != BindingEffect::Pure ||
        binding->entryPoints.pure.empty())
      return generatorError("ACLOWER-INLINE-EFFECT",
                            "pure expression has no exact entry point");
    std::string result = binding->entryPoints.pure + "(";
    for (auto [index, argument] : llvm::enumerate(expression->arguments)) {
      auto emitted = moduleValueExpression(plan, module, argument);
      if (!emitted)
        return emitted.takeError();
      if (index != 0)
        result.append(", ");
      result.append(*emitted);
    }
    return result.append(")");
  }

  auto exported = std::find_if(module.exports.begin(), module.exports.end(),
                               [&](const ExportPlan &candidate) {
                                 return candidate.resultValue == value;
                               });
  if (exported != module.exports.end())
    return moduleValueExpression(plan, module, exported->sourceValue);
  return generatorError("ACLOWER-OWNERSHIP",
                        "module value has no structured realization");
}

llvm::Expected<std::string> arrayInitializer(const ModelPlan &plan,
                                             const PlacementPlan &placement,
                                             size_t dimension,
                                             std::vector<uint64_t> &indices) {
  std::string result = "{";
  const uint64_t extent = placement.shape[dimension];
  for (uint64_t index = 0; index < extent; ++index) {
    if (index != 0)
      result.append(", ");
    indices.push_back(index);
    if (dimension + 1 != placement.shape.size()) {
      auto nested = arrayInitializer(plan, placement, dimension + 1, indices);
      if (!nested)
        return nested.takeError();
      result.append(*nested);
    } else {
      llvm::StringRef target = placement.target;
      target = target.take_until([](char value) { return value == ':'; });
      const BindingPlan *binding = findBinding(plan, target);
      const ModulePlan *nestedModule = findModule(plan, target);
      const TypePlan *runtimeType = findType(plan, target);
      if (runtimeType && runtimeType->kind != TypeKind::RuntimeObject)
        runtimeType = nullptr;
      if (!binding && !nestedModule && !runtimeType)
        return generatorError("ACLOWER-TYPE-MISMATCH",
                              "array target has no typed realization");
      auto type = placementType(plan, PlacementPlan{.target = target.str()});
      if (!type)
        return type.takeError();
      result.append(*type).append("(\"").append(placement.symbol);
      for (uint64_t element : indices)
        result.append("[").append(std::to_string(element)).append("]");
      if (binding) {
        auto suffix = constructorSuffix(*binding);
        if (!suffix)
          return suffix.takeError();
        result.append("\", nextObjectId++, this").append(*suffix).append(")");
      } else if (nestedModule) {
        result.append("\", gfsim::kInvalidObjectId, this, nextObjectId)");
      } else {
        result.append("\", nextObjectId++, this");
        for (const llvm::json::Value &argument : placement.staticArguments) {
          auto literal = cppLiteral(argument);
          if (!literal)
            return literal.takeError();
          result.append(", ").append(*literal);
        }
        result.push_back(')');
      }
    }
    indices.pop_back();
  }
  result.append("}");
  return result;
}

llvm::Expected<GeneratedFile> moduleSource(const ModelPlan &plan,
                                           const ModulePlan &module) {
  std::vector<std::string> initializers;
  for (const PlacementPlan &placement : module.placements) {
    if (placement.kind == PlacementKind::GeneratedModule) {
      initializers.push_back(placement.memberName + "(\"" + placement.symbol +
                             "\", gfsim::kInvalidObjectId, this, "
                             "nextObjectId)");
      continue;
    }
    llvm::StringRef target = placement.target;
    target = target.take_until([](char value) { return value == ':'; });
    const BindingPlan *binding = findBinding(plan, target);
    const ModulePlan *nestedModule = findModule(plan, target);
    const TypePlan *runtimeType = findType(plan, target);
    if (runtimeType && runtimeType->kind != TypeKind::RuntimeObject)
      runtimeType = nullptr;
    if (!binding && !nestedModule && !runtimeType)
      return generatorError("ACLOWER-BINDING-MISSING",
                            "placement has no selected binding");
    if (placement.shape.empty()) {
      if (runtimeType) {
        std::string initializer = placement.memberName + "(\"" +
                                  placement.symbol + "\", nextObjectId++, this";
        switch (placement.kind) {
        case PlacementKind::CompilerNativeFlowLink: {
          size_t flowOrdinal = 0;
          const BindPlan *flowBind = nullptr;
          for (const BindPlan &candidate : module.binds) {
            if (candidate.kind != "flow")
              continue;
            if (placement.symbol ==
                llvm::formatv("zz_flow_link_{0:08}", flowOrdinal).str()) {
              flowBind = &candidate;
              break;
            }
            ++flowOrdinal;
          }
          if (!flowBind)
            return generatorError("ACLOWER-OWNERSHIP",
                                  "QueueLink placement has no flow bind");
          auto source =
              moduleValueExpression(plan, module, flowBind->sourceValue);
          auto target =
              moduleValueExpression(plan, module, flowBind->targetValue);
          if (!source)
            return source.takeError();
          if (!target)
            return target.takeError();
          initializer.append(", ").append(*source).append(", ").append(*target);
          initializer.push_back(')');
          initializers.push_back(std::move(initializer));
          continue;
        }
        default:
          break;
        }
        for (const llvm::json::Value &argument : placement.staticArguments) {
          auto literal = cppLiteral(argument);
          if (!literal)
            return literal.takeError();
          initializer.append(", ").append(*literal);
        }
        initializer.push_back(')');
        initializers.push_back(std::move(initializer));
        continue;
      }
      if (!binding)
        return generatorError("ACLOWER-OWNERSHIP",
                              "generated module placement kind is invalid");
      auto suffix = constructorSuffix(*binding);
      if (!suffix)
        return suffix.takeError();
      initializers.push_back(placement.memberName + "(\"" + placement.symbol +
                             "\", nextObjectId++, this" + *suffix + ")");
    } else {
      std::vector<uint64_t> indices;
      auto initializer = arrayInitializer(plan, placement, 0, indices);
      if (!initializer)
        return initializer.takeError();
      initializers.push_back(placement.memberName + *initializer);
    }
  }
  for (const ProcessPlan &process : module.processes) {
    std::string initializer =
        process.symbol + "_(\"" + process.symbol + "\", nextObjectId++, this";
    for (const CapturePlan &capture : process.captures) {
      auto expression =
          moduleValueExpression(plan, module, capture.sourceValue);
      if (!expression)
        return expression.takeError();
      initializer.append(", ").append(*expression);
    }
    initializer.append(")");
    initializers.push_back(std::move(initializer));
  }

  std::ostringstream output;
  output << "#include \"generated/modules/" << module.className
         << ".h\"\n\n#include <stdexcept>\n\nnamespace acsim_generated {\n\n";
  if (std::any_of(module.binds.begin(), module.binds.end(),
                  [](const BindPlan &bind) {
                    return bind.kind != "pure_view" && bind.kind != "flow";
                  }))
    output << "namespace {\ntemplate <typename Source, typename Target>\n"
              "void bindStatic(Source &&source, Target &&target) {\n"
              "  if constexpr (requires { source.bind(target); })\n"
              "    source.bind(target);\n"
              "  else if constexpr (requires { target.bind(source); })\n"
              "    target.bind(source);\n"
              "  else\n"
              "    static_assert(sizeof(Source) == 0, "
              "\"ACLOWER-TYPE-MISMATCH\");\n"
              "}\n} // namespace\n\n";
  output << module.className << "::" << module.className
         << "(std::string name, gfsim::ObjectId id, gfsim::SimObject *parent, "
            "gfsim::ObjectId &nextObjectId)\n"
            "    : gfsim::Module(std::move(name), id, parent)";
  for (const std::string &initializer : initializers)
    output << ",\n    " << initializer;
  output << " {\n";
  for (const PlacementPlan &placement : module.placements) {
    if (placement.shape.empty()) {
      output << "  if (!attachChild(" << placement.memberName << "))\n"
             << "    throw std::logic_error(\"ACLOWER-OWNERSHIP\");\n";
    } else {
      std::string range = placement.memberName;
      for (size_t dimension = 0; dimension < placement.shape.size();
           ++dimension) {
        output << std::string(2 + dimension * 2, ' ') << "for (auto &element"
               << dimension << " : " << range << ") {\n";
        range = "element" + std::to_string(dimension);
      }
      output << std::string(2 + placement.shape.size() * 2, ' ')
             << "if (!attachChild(" << range << "))\n"
             << std::string(4 + placement.shape.size() * 2, ' ')
             << "throw std::logic_error(\"ACLOWER-OWNERSHIP\");\n";
      for (size_t dimension = placement.shape.size(); dimension > 0;
           --dimension)
        output << std::string(2 + (dimension - 1) * 2, ' ') << "}\n";
    }
  }
  for (const ProcessPlan &process : module.processes)
    output << "  if (!attachChild(" << process.symbol << "_))\n"
           << "    throw std::logic_error(\"ACLOWER-OWNERSHIP\");\n";
  for (const BindPlan &bind : module.binds) {
    if (bind.kind == "pure_view" || bind.kind == "flow")
      continue;
    auto source = moduleValueExpression(plan, module, bind.sourceValue);
    auto target = moduleValueExpression(plan, module, bind.targetValue);
    if (!source)
      return source.takeError();
    if (!target)
      return target.takeError();
    output << "  bindStatic(" << *source << ", " << *target << ");\n";
  }
  output << "}\n";
  for (const ExportPlan &exported : module.exports) {
    if (llvm::StringRef(exported.resultType).starts_with("!acsim.port<"))
      continue;
    auto expression = moduleValueExpression(plan, module, exported.sourceValue);
    if (!expression)
      return expression.takeError();
    output << "\ndecltype(auto) " << module.className << "::" << exported.symbol
           << "() { return " << *expression << "; }\n"
           << "decltype(auto) " << module.className << "::" << exported.symbol
           << "() const { return " << *expression << "; }\n";
  }
  output << "\n} // namespace acsim_generated\n";
  return makeFile("src/generated/modules/" + module.className + ".cpp",
                  output.str());
}

llvm::Expected<std::string>
runtimeObjectExpression(const ModelPlan &plan,
                        const RuntimeObjectPlan &runtimeObject) {
  const ModulePlan *module = rootModule(plan);
  if (!module)
    return generatorError("ACLOWER-OWNERSHIP",
                          "root module has no generated specialization");

  llvm::SmallVector<llvm::StringRef> segments;
  llvm::StringRef(runtimeObject.hierarchyPath).split(segments, '.');
  if (segments.size() < 2)
    return generatorError("ACLOWER-DISPATCH",
                          "runtime path has no hierarchy segments");
  std::string expression = "model.top_";
  for (size_t segmentIndex = 1; segmentIndex < segments.size();
       ++segmentIndex) {
    llvm::StringRef segment = segments[segmentIndex];
    llvm::StringRef symbol =
        segment.take_until([](char value) { return value == '['; });
    auto placement =
        std::find_if(module->placements.begin(), module->placements.end(),
                     [&](const PlacementPlan &candidate) {
                       return candidate.symbol == symbol;
                     });
    if (placement != module->placements.end()) {
      expression.append(".").append(placement->memberName);
      llvm::StringRef indices = segment.drop_front(symbol.size());
      while (!indices.empty()) {
        if (!indices.consume_front("["))
          return generatorError("ACLOWER-ARRAY",
                                "runtime path index is malformed");
        if (!indices.contains(']'))
          return generatorError("ACLOWER-ARRAY",
                                "runtime path index is unterminated");
        auto [index, rest] = indices.split(']');
        expression.append("[").append(index.str()).append("]");
        indices = rest;
      }
      if (segmentIndex + 1 != segments.size()) {
        llvm::StringRef target = placement->target;
        target = target.take_until([](char value) { return value == ':'; });
        module = findModule(plan, target);
        if (!module)
          return generatorError("ACLOWER-DISPATCH",
                                "runtime path crosses a non-module member");
      }
      continue;
    }
    auto process =
        std::find_if(module->processes.begin(), module->processes.end(),
                     [&](const ProcessPlan &candidate) {
                       return candidate.symbol == symbol;
                     });
    if (process == module->processes.end() ||
        segmentIndex + 1 != segments.size())
      return generatorError("ACLOWER-DISPATCH",
                            "runtime path has no generated member");
    expression.append(".").append(process->symbol).append("_");
  }
  return expression;
}

llvm::Expected<const PlacementPlan *>
runtimeObjectPlacement(const ModelPlan &plan,
                       const RuntimeObjectPlan &runtimeObject) {
  const ModulePlan *module = rootModule(plan);
  if (!module)
    return generatorError("ACLOWER-OWNERSHIP",
                          "root module has no generated specialization");
  llvm::SmallVector<llvm::StringRef> segments;
  llvm::StringRef(runtimeObject.hierarchyPath).split(segments, '.');
  if (segments.size() < 2)
    return generatorError("ACLOWER-DISPATCH",
                          "runtime path has no hierarchy segments");
  for (size_t segmentIndex = 1; segmentIndex < segments.size();
       ++segmentIndex) {
    llvm::StringRef symbol = segments[segmentIndex].take_until(
        [](char value) { return value == '['; });
    auto placement =
        std::find_if(module->placements.begin(), module->placements.end(),
                     [&](const PlacementPlan &candidate) {
                       return candidate.symbol == symbol;
                     });
    if (placement == module->placements.end())
      return static_cast<const PlacementPlan *>(nullptr);
    if (segmentIndex + 1 == segments.size())
      return &*placement;
    llvm::StringRef target = placement->target;
    target = target.take_until([](char value) { return value == ':'; });
    module = findModule(plan, target);
    if (!module)
      return generatorError("ACLOWER-DISPATCH",
                            "runtime path crosses a non-module member");
  }
  return static_cast<const PlacementPlan *>(nullptr);
}

llvm::Expected<GeneratedFile> dispatchHeader(const ModelPlan &plan) {
  std::vector<uint32_t> offsets(plan.runtimeObjects.size() + 1, 0);
  std::vector<uint32_t> targets;
  size_t edgeIndex = 0;
  for (size_t source = 0; source < plan.runtimeObjects.size(); ++source) {
    while (edgeIndex < plan.activationEdges.size() &&
           plan.activationEdges[edgeIndex].sourceId == source) {
      targets.push_back(plan.activationEdges[edgeIndex].targetId);
      ++edgeIndex;
    }
    offsets[source + 1] = static_cast<uint32_t>(targets.size());
  }

  std::ostringstream output;
  output << "#pragma once\n\n#include \"generated/model.h\"\n"
            "#include \"gfsim/dispatch.h\"\n\n#include <array>\n\n"
            "namespace acsim_generated {\n\nstruct DispatchAccess {\n"
            "  static std::array<gfsim::DispatchRow, "
         << plan.runtimeObjects.size() << "> makeRows(Model &model) {\n"
         << "    return {";
  for (auto [index, runtimeObject] : llvm::enumerate(plan.runtimeObjects)) {
    auto expression = runtimeObjectExpression(plan, runtimeObject);
    if (!expression)
      return expression.takeError();
    if (index != 0)
      output << ", ";
    output << "gfsim::makeDispatchRow(&" << *expression << ")";
  }
  output << "};\n  }\n};\n\ninline constexpr std::array<uint32_t, "
         << offsets.size() << "> kActivationOffsets = {";
  for (auto [index, offset] : llvm::enumerate(offsets)) {
    if (index != 0)
      output << ", ";
    output << offset;
  }
  output << "};\ninline constexpr std::array<gfsim::ObjectId, "
         << targets.size() << "> kActivationTargets = {";
  for (auto [index, target] : llvm::enumerate(targets)) {
    if (index != 0)
      output << ", ";
    output << target;
  }
  output << "};\n\n} // namespace acsim_generated\n";
  return makeFile("include/generated/dispatch.h", output.str());
}

llvm::Expected<GeneratedFile> modelHeader(const ModelPlan &plan,
                                          llvm::StringRef fingerprint) {
  const ModulePlan *root = rootModule(plan);
  if (!root)
    return generatorError("ACLOWER-OWNERSHIP",
                          "root module has no generated specialization");
  const auto hostInputs = rootHostInputs(plan);
  const auto hostOutputs = rootHostOutputs(plan);
  std::ostringstream output;
  output
      << "#pragma once\n\n#include \"generated/modules/" << root->className
      << ".h\"\n#include \"gfsim/dispatch.h\"\n#include \"gfsim/harness.h\"\n"
         "#include \"gfsim/host.h\"\n"
         "#include \"gfsim/object.h\"\n\n"
         "#include <array>\n#include <cstddef>\n#include <span>\n#include <string_view>\n#include <vector>\n\n"
         "namespace acsim_generated {\n\ninline constexpr std::string_view "
         "kBuildFingerprint = \""
      << fingerprint.str()
      << "\";\n\ninline constexpr std::array<gfsim::TimeDomainRuntime, "
      << plan.timeDomains.size() << "> kTimeDomains = {{";
  for (auto [index, domain] : llvm::enumerate(plan.timeDomains)) {
    if (index != 0)
      output << ", ";
    output << "gfsim::TimeDomainRuntime{\"" << domain.name << "\", "
           << domain.period << ", " << domain.phase << ", " << domain.tickScale
           << "}";
  }
  output
      << "}};\n\nstruct DispatchAccess;\n\nclass Model final {\n"
         "public:\n  Model();\n  void configure(const gfsim::RuntimeLimits "
         "&limits);\n  bool loadTrace(gfsim::PtoTraceDocument document);\n  "
         "gfsim::TerminationResult run();\n  bool stepTick();\n  "
         "gfsim::Epoch currentEpoch() const { return system_.currentEpoch(); }\n  "
         "gfsim::TerminationResult terminationResult() const { return "
         "system_.terminationResult(); }\n  "
         "std::size_t hostInputCount() const;\n  std::string_view "
         "hostInputName(std::size_t index) const;\n  bool hostInputReady(std::size_t "
         "index) const;\n  bool offer(std::size_t index, int32_t value);\n  "
         "bool offerBytes(std::size_t index, std::span<const std::byte> bytes);\n  void reset();\n  "
         "std::size_t hostOutputCount() const;\n  std::string_view hostOutputName(std::size_t index) const;\n  "
         "std::size_t hostOutputSize(std::size_t index) const;\n  bool hostOutputReady(std::size_t index) const;\n  "
         "bool takeBytes(std::size_t index, std::span<std::byte> bytes);\n  "
         "std::string_view "
         "buildFingerprint() const { return kBuildFingerprint; }\n  "
         "std::span<const gfsim::TimeDomainRuntime> timeDomains() const { "
         "return kTimeDomains; }\n  std::vector<gfsim::StatSnapshot> "
         "statistics() const { return system_.statistics(); }\n  "
         "std::span<const gfsim::CommittedEvent> observations() const { "
         "return system_.observations(); }\n\nprivate:\n "
         " "
         "friend struct "
         "DispatchAccess;\n  static constexpr std::size_t kTraceOwnerCount = "
      << std::count_if(
             plan.runtimeObjects.begin(), plan.runtimeObjects.end(),
             [](const RuntimeObjectPlan &object) { return object.traceOwner; })
      << ";\n  "
      << "gfsim::SimSystem system_;\n  gfsim::ObjectId nextObjectId_ = 0;\n  "
      << root->className << " top_;\n";
  for (const PlacementPlan *input : hostInputs) {
    auto cpp = hostInputCppType(plan, *input);
    if (!cpp)
      return cpp.takeError();
    output << "  gfsim::HostIngress<" << *cpp << "> host_"
           << input->memberName << ";\n";
  }
  for (const PlacementPlan *outputPlacement : hostOutputs) {
    auto cpp = hostInputCppType(plan, *outputPlacement);
    if (!cpp)
      return cpp.takeError();
    output << "  gfsim::HostEgress<" << *cpp << "> host_out_"
           << outputPlacement->memberName << ";\n";
  }
  output << "  bool steppingStarted_ = false;\n"
      << "  std::array<gfsim::DispatchRow, " << plan.runtimeObjects.size()
      << "> dispatch_;\n};\n\n} // namespace acsim_generated\n";
  return makeFile("include/generated/model.h", output.str());
}

llvm::Expected<GeneratedFile> modelSource(const ModelPlan &plan) {
  const auto hostInputs = rootHostInputs(plan);
  const auto hostOutputs = rootHostOutputs(plan);
  uint64_t eventCapacity = 1024;
  for (const RuntimeObjectPlan &object : plan.runtimeObjects) {
    auto placement = runtimeObjectPlacement(plan, object);
    if (!placement)
      return placement.takeError();
    if (!*placement)
      continue;
    const TypePlan *type = findType(plan, (*placement)->target);
    if (!type ||
        !llvm::StringRef(type->cppType).starts_with("gfsim::TimedEventQueue<"))
      continue;
    if ((*placement)->staticArguments.empty())
      return generatorError("ACLOWER-CAPACITY",
                            "timed event queue has no capacity argument");
    auto capacity = (*placement)->staticArguments.front().getAsInteger();
    if (!capacity || *capacity <= 0)
      return generatorError("ACLOWER-CAPACITY",
                            "timed event queue capacity is invalid");
    const uint64_t addition = static_cast<uint64_t>(*capacity);
    if (eventCapacity > std::numeric_limits<uint64_t>::max() - addition)
      return generatorError("ACLOWER-CAPACITY",
                            "internal event queue capacity overflow");
    eventCapacity += addition;
  }
  std::ostringstream output;
  output << "#include \"generated/dispatch.h\"\n\n#include <algorithm>\n"
            "#include <cstring>\n#include <stdexcept>\n#include <utility>\n\n"
            "namespace acsim_generated {\n\nModel::Model()\n"
            "    : system_(\"generated\"),\n"
            "      nextObjectId_(0),\n"
            "      top_(\"root-model\", gfsim::kRootObjectId - 1, "
            "&system_.root(), nextObjectId_),\n";
  for (const PlacementPlan *input : hostInputs)
    output << "      host_" << input->memberName << "(\"host_"
           << input->symbol << "\", nextObjectId_++, &top_, top_."
           << input->memberName << "),\n";
  for (const PlacementPlan *outputPlacement : hostOutputs)
    output << "      host_out_" << outputPlacement->memberName << "(\"host_out_"
           << outputPlacement->symbol << "\", nextObjectId_++, &top_, top_."
           << outputPlacement->memberName << "),\n";
  output << "      dispatch_(DispatchAccess::makeRows(*this)) {\n"
            "  if (!system_.root().attachChild(top_))\n"
            "    throw std::logic_error(\"ACLOWER-OWNERSHIP\");\n"
            "  bool hostAttached = true;\n";
  for (const PlacementPlan *input : hostInputs)
    output << "  hostAttached = top_.attachChild(host_" << input->memberName
           << ") && hostAttached;\n"
           << "  system_.registerObject(&host_" << input->memberName
           << ");\n";
  for (const PlacementPlan *outputPlacement : hostOutputs)
    output << "  hostAttached = top_.attachChild(host_out_"
           << outputPlacement->memberName << ") && hostAttached;\n"
           << "  system_.registerObject(&host_out_"
           << outputPlacement->memberName << ");\n";
  output << "  if (!hostAttached)\n"
            "    throw std::logic_error(\"ACLOWER-HOST-INPUT\");\n"
            "  const bool capacityConfigured = "
            "system_.setEventQueueCapacity("
         << eventCapacity
         << ");\n  if (!capacityConfigured)\n"
            "    throw std::logic_error(\"ACLOWER-CAPACITY\");\n"
            "  for (gfsim::DispatchRow &row : dispatch_) {\n"
            "    auto *object = static_cast<gfsim::SimObject *>(row.object);\n"
            "    object->bindSystem(&system_);\n"
            "    object->setObservationSink(&system_);\n"
            "  }\n"
            "  if (!system_.setDispatchTable(dispatch_))\n"
            "    throw std::logic_error(\"ACLOWER-DISPATCH\");\n"
            "  if (!system_.setActivationPlan(kActivationOffsets, "
            "kActivationTargets))\n"
            "    throw std::logic_error(\"ACLOWER-ACTIVATION\");\n"
            "  if (!system_.setTimeDomains(kTimeDomains))\n"
            "    throw std::logic_error(\"ACLOWER-TIME-DOMAIN\");\n"
            "}\n\nvoid Model::configure(const gfsim::RuntimeLimits &limits) {\n"
            "  if (!system_.setRuntimeLimits(limits))\n"
            "    throw std::logic_error(\"ACRUN-LIMITS\");\n"
            "}\n\nbool Model::loadTrace(gfsim::PtoTraceDocument document) {\n";
  const auto traceOwnerCount = std::count_if(
      plan.runtimeObjects.begin(), plan.runtimeObjects.end(),
      [](const RuntimeObjectPlan &object) { return object.traceOwner; });
  if (traceOwnerCount == 0) {
    output << "  return document.records.empty();\n";
  } else if (traceOwnerCount == 1) {
    const RuntimeObjectPlan &traceOwner = *std::find_if(
        plan.runtimeObjects.begin(), plan.runtimeObjects.end(),
        [](const RuntimeObjectPlan &object) { return object.traceOwner; });
    auto expression = runtimeObjectExpression(plan, traceOwner);
    if (!expression)
      return expression.takeError();
    llvm::StringRef memberExpression(*expression);
    if (!memberExpression.consume_front("model."))
      return generatorError("ACLOWER-DISPATCH",
                            "trace owner expression is not model-relative");
    output << "  return " << memberExpression.str()
           << ".loadDocument(std::move(document));\n";
  } else {
    output << "  return false;\n";
  }
  output << "}\n\ngfsim::TerminationResult Model::run() {\n"
            "  return system_.run();\n}\n\n"
            "std::size_t Model::hostInputCount() const { return "
         << hostInputs.size() << "; }\n\n"
            "std::string_view Model::hostInputName(std::size_t index) const {\n"
            "  static constexpr std::array<std::string_view, "
         << hostInputs.size() << "> names = {";
  for (auto [index, input] : llvm::enumerate(hostInputs)) {
    if (index != 0)
      output << ", ";
    auto literal = cppLiteral(llvm::json::Value(input->hostInput));
    if (!literal)
      return literal.takeError();
    output << *literal;
  }
  output << "};\n  return index < names.size() ? names[index] : "
            "std::string_view{};\n}\n\n"
            "bool Model::hostInputReady(std::size_t index) const {\n"
            "  switch (index) {\n";
  for (auto [index, input] : llvm::enumerate(hostInputs))
    output << "  case " << index << ": return !host_" << input->memberName
           << ".mailboxOccupied();\n";
  output << "  default: return false;\n  }\n}\n\n"
            "bool Model::offer(std::size_t index, int32_t value) {\n"
            "  if (system_.isTerminated()) return false;\n"
            "  switch (index) {\n";
  for (auto [index, input] : llvm::enumerate(hostInputs)) {
    auto cpp = hostInputCppType(plan, *input);
    if (!cpp)
      return cpp.takeError();
    output << "  case " << index << ": ";
    if (*cpp == "std::int32_t")
      output << "return host_" << input->memberName << ".stage(value);\n";
    else
      output << "return false;\n";
  }
  output << "  default: return false;\n  }\n}\n\n"
            "bool Model::offerBytes(std::size_t index, std::span<const std::byte> bytes) {\n"
            "  if (system_.isTerminated()) return false;\n"
            "  switch (index) {\n";
  for (auto [index, input] : llvm::enumerate(hostInputs)) {
    auto cpp = hostInputCppType(plan, *input);
    if (!cpp)
      return cpp.takeError();
    output << "  case " << index << ": {\n    " << *cpp << " value{};\n";
    if (llvm::StringRef(*cpp).starts_with("gfsim::AtomicPacket<"))
      output << "    if (bytes.size() != value.bytes.size()) return false;\n"
                "    std::copy(bytes.begin(), bytes.end(), value.bytes.begin());\n";
    else
      output << "    if (bytes.size() != sizeof(value)) return false;\n"
                "    std::memcpy(&value, bytes.data(), sizeof(value));\n";
    output << "    return host_" << input->memberName
           << ".stage(value);\n  }\n";
  }
  output << "  default: return false;\n  }\n}\n\n"
            "std::size_t Model::hostOutputCount() const { return "
         << hostOutputs.size() << "; }\n\n"
            "std::string_view Model::hostOutputName(std::size_t index) const {\n"
            "  static constexpr std::array<std::string_view, "
         << hostOutputs.size() << "> names = {";
  for (auto [index, outputPlacement] : llvm::enumerate(hostOutputs)) {
    if (index)
      output << ", ";
    auto literal = cppLiteral(llvm::json::Value(outputPlacement->hostOutput));
    if (!literal)
      return literal.takeError();
    output << *literal;
  }
  output << "};\n  return index < names.size() ? names[index] : std::string_view{};\n}\n\n"
            "std::size_t Model::hostOutputSize(std::size_t index) const {\n"
            "  switch (index) {\n";
  for (auto [index, outputPlacement] : llvm::enumerate(hostOutputs)) {
    auto cpp = hostInputCppType(plan, *outputPlacement);
    if (!cpp)
      return cpp.takeError();
    output << "  case " << index << ": return sizeof(" << *cpp << ");\n";
  }
  output << "  default: return 0;\n  }\n}\n\n"
            "bool Model::hostOutputReady(std::size_t index) const {\n"
            "  switch (index) {\n";
  for (auto [index, outputPlacement] : llvm::enumerate(hostOutputs))
    output << "  case " << index << ": return host_out_"
           << outputPlacement->memberName << ".ready();\n";
  output << "  default: return false;\n  }\n}\n\n"
            "bool Model::takeBytes(std::size_t index, std::span<std::byte> bytes) {\n"
            "  switch (index) {\n";
  for (auto [index, outputPlacement] : llvm::enumerate(hostOutputs)) {
    auto cpp = hostInputCppType(plan, *outputPlacement);
    if (!cpp)
      return cpp.takeError();
    output << "  case " << index << ": {\n    auto value = host_out_"
           << outputPlacement->memberName << ".take();\n"
           << "    if (!value || bytes.size() != sizeof(" << *cpp
           << ")) return false;\n";
    if (llvm::StringRef(*cpp).starts_with("gfsim::AtomicPacket<"))
      output << "    std::copy(value->bytes.begin(), value->bytes.end(), bytes.begin());\n";
    else
      output << "    std::memcpy(bytes.data(), &*value, sizeof(*value));\n";
    output << "    return true;\n  }\n";
  }
  output << "  default: return false;\n  }\n}\n\n"
            "bool Model::stepTick() {\n"
            "  if (system_.isTerminated()) return false;\n"
            "  const gfsim::Epoch start = system_.currentEpoch();\n"
            "  if (!steppingStarted_) {\n";
  for (const RuntimeObjectPlan &object : plan.runtimeObjects)
    if (object.objectKind == RuntimeObjectKind::Process)
      output << "    if (!system_.scheduleWork(" << object.objectId
             << ", start)) return false;\n";
  output << "    steppingStarted_ = true;\n  }\n";
  for (const PlacementPlan *input : hostInputs)
    output << "  if (!system_.scheduleWork(host_" << input->memberName
           << ".id(), start) || !system_.scheduleWork(host_"
           << input->memberName
           << ".id(), {start.time + 1, 0})) return false;\n";
  for (const PlacementPlan *outputPlacement : hostOutputs)
    output << "  if (!system_.scheduleWork(host_out_"
           << outputPlacement->memberName << ".id(), start)) return false;\n";
  output << "  do {\n"
            "    if (!system_.step() && system_.currentEpoch().time == start.time)\n"
            "      return false;\n"
            "  } while (!system_.isTerminated() &&\n"
            "           system_.currentEpoch().time == start.time);\n"
            "  return !system_.isTerminated();\n}\n\n"
            "void Model::reset() {\n  system_.reset();\n";
  for (const PlacementPlan *input : hostInputs)
    output << "  host_" << input->memberName << ".reset();\n";
  for (const PlacementPlan *outputPlacement : hostOutputs)
    output << "  host_out_" << outputPlacement->memberName << ".reset();\n";
  output << "  steppingStarted_ = false;\n}\n\n"
            "} // namespace acsim_generated\n";
  return makeFile("src/generated/model.cpp", output.str());
}

GeneratedFile mainSource() {
  return makeFile(
      "src/generated/main.cpp",
      "#include \"generated/model.h\"\n\n#include \"llvm/Support/Error.h\"\n\n"
      "#include <filesystem>\n#include <fstream>\n#include "
      "<iostream>\n#include "
      "<iterator>\n#include <string>\n#include <string_view>\n\nnamespace "
      "{\n\nint "
      "exitCode(gfsim::RunStatus status) {\n  switch (status) {\n  case "
      "gfsim::RunStatus::Completed:\n    return 0;\n  case "
      "gfsim::RunStatus::Incomplete:\n    return 7;\n  case "
      "gfsim::RunStatus::Failed:\n    return 6;\n  }\n  return 6;\n}\n\nint "
      "exitCode(gfsim::TerminationClass classification) {\n  switch "
      "(classification) {\n  case gfsim::TerminationClass::Completed:\n    "
      "return "
      "0;\n  case gfsim::TerminationClass::Incomplete:\n    return 7;\n  case "
      "gfsim::TerminationClass::Failed:\n    return 6;\n  }\n  return "
      "6;\n}\n\n} "
      "// namespace\n\nint main(int argc, char **argv) {\n  if (argc == 2 && "
      "std::string_view(argv[1]) == \"--build-fingerprint\") {\n    std::cout "
      "<< acsim_generated::kBuildFingerprint << '\\n';\n    return 0;\n  }\n\n "
      " "
      "acsim_generated::Model model;\n  if (argc == 1) {\n    "
      "model.configure({});\n    return "
      "exitCode(model.run().classification);\n  "
      "}\n  if (argc != 5 || std::string_view(argv[1]) != \"--run-manifest\" "
      "||\n"
      "      std::string_view(argv[3]) != \"--run-result-stage\")\n    return "
      "2;\n\n  std::ifstream input(argv[2], std::ios::binary);\n  if "
      "(!input)\n    "
      "return 5;\n  std::string "
      "bytes((std::istreambuf_iterator<char>(input)),\n"
      "                    std::istreambuf_iterator<char>());\n  "
      "std::filesystem::path "
      "manifestPath(argv[2]);\n  auto manifest = gfsim::loadRunManifest(\n     "
      " "
      "bytes, manifestPath.parent_path().string());\n  if (!manifest) {\n    "
      "std::cerr << llvm::toString(manifest.takeError()) << '\\n';\n    return "
      "5;\n  }\n  auto result =\n      gfsim::runGeneratedModel(model, "
      "*manifest, "
      "argv[4]);\n  if (!result) {\n    std::cerr << "
      "llvm::toString(result.takeError()) << '\\n';\n    return 5;\n  }\n  "
      "return "
      "exitCode(result->status);\n}\n");
}

GeneratedFile cApiHeader() {
  return makeFile("include/generated/c_api.h", R"cpp(#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct ac_model ac_model;
uint32_t ac_model_abi_version(void);
ac_model *ac_model_create(void);
void ac_model_destroy(ac_model *model);
size_t ac_model_host_input_count(const ac_model *model);
const char *ac_model_host_input_name(const ac_model *model, size_t index);
int ac_model_host_input_ready(const ac_model *model, size_t index);
int ac_model_offer(ac_model *model, size_t index, int32_t value);
int ac_model_offer_bytes(ac_model *model, size_t index, const uint8_t *bytes, size_t size);
size_t ac_model_host_output_count(const ac_model *model);
const char *ac_model_host_output_name(const ac_model *model, size_t index);
size_t ac_model_host_output_size(const ac_model *model, size_t index);
int ac_model_host_output_ready(const ac_model *model, size_t index);
int ac_model_take_bytes(ac_model *model, size_t index, uint8_t *bytes, size_t size);
size_t ac_model_offer_batch(ac_model *model, const size_t *indices, const int32_t *values, size_t count);
int ac_model_step_tick(ac_model *model);
uint64_t ac_model_tick(const ac_model *model);
void ac_model_reset(ac_model *model);
size_t ac_model_stat_count(ac_model *model);
const char *ac_model_stat_name(const ac_model *model, size_t index);
const char *ac_model_stat_path(const ac_model *model, size_t index);
uint64_t ac_model_stat_value(const ac_model *model, size_t index);
const char *ac_model_last_error(const ac_model *model);
#ifdef __cplusplus
}
#endif
)cpp");
}

GeneratedFile cApiSource() {
  return makeFile("src/generated/c_api.cpp", R"cpp(#include "generated/c_api.h"
#include "generated/model.h"
#include <exception>
#include <string>
#include <vector>
struct ac_model { acsim_generated::Model model; std::vector<gfsim::StatSnapshot> stats; std::string error; };
extern "C" {
uint32_t ac_model_abi_version(void) { return 2; }
ac_model *ac_model_create(void) { try { return new ac_model; } catch (...) { return nullptr; } }
void ac_model_destroy(ac_model *model) { delete model; }
size_t ac_model_host_input_count(const ac_model *model) { return model ? model->model.hostInputCount() : 0; }
const char *ac_model_host_input_name(const ac_model *model, size_t index) { if (!model) return nullptr; auto name = model->model.hostInputName(index); return name.empty() ? nullptr : name.data(); }
int ac_model_host_input_ready(const ac_model *model, size_t index) { return model && model->model.hostInputReady(index) ? 1 : 0; }
int ac_model_offer(ac_model *model, size_t index, int32_t value) { if (!model || index >= model->model.hostInputCount()) return -1; return model->model.offer(index, value) ? 1 : 0; }
int ac_model_offer_bytes(ac_model *model, size_t index, const uint8_t *bytes, size_t size) { if (!model || index >= model->model.hostInputCount() || (!bytes && size)) return -1; auto view = std::span<const std::byte>(reinterpret_cast<const std::byte *>(bytes), size); return model->model.offerBytes(index, view) ? 1 : 0; }
size_t ac_model_host_output_count(const ac_model *model) { return model ? model->model.hostOutputCount() : 0; }
const char *ac_model_host_output_name(const ac_model *model, size_t index) { if (!model) return nullptr; auto name = model->model.hostOutputName(index); return name.empty() ? nullptr : name.data(); }
size_t ac_model_host_output_size(const ac_model *model, size_t index) { return model ? model->model.hostOutputSize(index) : 0; }
int ac_model_host_output_ready(const ac_model *model, size_t index) { return model && model->model.hostOutputReady(index) ? 1 : 0; }
int ac_model_take_bytes(ac_model *model, size_t index, uint8_t *bytes, size_t size) { if (!model || index >= model->model.hostOutputCount() || (!bytes && size)) return -1; auto view = std::span<std::byte>(reinterpret_cast<std::byte *>(bytes), size); return model->model.takeBytes(index, view) ? 1 : 0; }
size_t ac_model_offer_batch(ac_model *model, const size_t *indices, const int32_t *values, size_t count) { if (!model || (!indices && count) || (!values && count)) return 0; size_t accepted = 0; for (size_t i = 0; i < count; ++i) if (ac_model_offer(model, indices[i], values[i]) == 1) ++accepted; return accepted; }
int ac_model_step_tick(ac_model *model) { if (!model) return -1; try { if (model->model.stepTick()) return 1; model->error = model->model.terminationResult().diagnosticCode; return 0; } catch (const std::exception &e) { model->error = e.what(); return -1; } }
uint64_t ac_model_tick(const ac_model *model) { return model ? model->model.currentEpoch().time : 0; }
void ac_model_reset(ac_model *model) { if (model) { model->model.reset(); model->stats.clear(); model->error.clear(); } }
size_t ac_model_stat_count(ac_model *model) { if (!model) return 0; model->stats = model->model.statistics(); return model->stats.size(); }
const char *ac_model_stat_name(const ac_model *model, size_t index) { return model && index < model->stats.size() ? model->stats[index].name.c_str() : nullptr; }
const char *ac_model_stat_path(const ac_model *model, size_t index) { return model && index < model->stats.size() ? model->stats[index].objectPath.c_str() : nullptr; }
uint64_t ac_model_stat_value(const ac_model *model, size_t index) { return model && index < model->stats.size() ? model->stats[index].value : 0; }
const char *ac_model_last_error(const ac_model *model) { return model ? model->error.c_str() : "null model"; }
}
)cpp");
}

std::vector<std::string> expectedPaths(const ModelPlan &plan) {
  std::vector<std::string> paths = {
      "include/generated/c_api.h", "include/generated/dispatch.h",
      "include/generated/model.h", "src/generated/c_api.cpp",
      "src/generated/main.cpp", "src/generated/model.cpp"};
  for (const ModulePlan &module : plan.modules) {
    paths.push_back("include/generated/modules/" + module.className + ".h");
    paths.push_back("src/generated/modules/" + module.className + ".cpp");
    for (const ProcessPlan &process : module.processes) {
      paths.push_back("include/generated/processes/" + process.className +
                      ".h");
      paths.push_back("src/generated/processes/" + process.className + ".cpp");
    }
  }
  std::sort(paths.begin(), paths.end());
  paths.erase(std::unique(paths.begin(), paths.end()), paths.end());
  return paths;
}

} // namespace

llvm::Expected<SourceBundle> generateModelSources(const ModelPlan &plan) {
  if (auto error = validateModelPlan(plan))
    return std::move(error);
  for (const BindingPlan &binding : plan.bindings) {
    const std::array entryPoints = {
        llvm::StringRef(binding.entryPoints.pure),
        llvm::StringRef(binding.entryPoints.reset),
        llvm::StringRef(binding.entryPoints.validate),
        llvm::StringRef(binding.entryPoints.work),
        llvm::StringRef(binding.entryPoints.xfer)};
    if (!isIncludePath(binding.header) || !isQualifiedName(binding.cppSymbol) ||
        !isQualifiedName(binding.conceptName) ||
        std::any_of(entryPoints.begin(), entryPoints.end(),
                    [](llvm::StringRef entryPoint) {
                      return !entryPoint.empty() &&
                             !isQualifiedName(entryPoint);
                    }))
      return generatorError("ACLOWER-PARAM-PHASE",
                            "binding contains an unsafe C++ token");
  }

  SourceBundle bundle;
  bundle.buildFingerprint = kGeneratedFingerprintPlaceholder.str();
  auto generatedDispatch = dispatchHeader(plan);
  if (!generatedDispatch)
    return generatedDispatch.takeError();
  auto generatedModel = modelHeader(plan, bundle.buildFingerprint);
  if (!generatedModel)
    return generatedModel.takeError();
  bundle.files.push_back(std::move(*generatedDispatch));
  bundle.files.push_back(std::move(*generatedModel));
  bundle.files.push_back(cApiHeader());
  bundle.files.push_back(cApiSource());
  bundle.files.push_back(mainSource());
  auto generatedModelSource = modelSource(plan);
  if (!generatedModelSource)
    return generatedModelSource.takeError();
  bundle.files.push_back(std::move(*generatedModelSource));
  for (const ModulePlan &module : plan.modules) {
    auto header = moduleHeader(plan, module);
    if (!header)
      return header.takeError();
    bundle.files.push_back(std::move(*header));
    auto source = moduleSource(plan, module);
    if (!source)
      return source.takeError();
    bundle.files.push_back(std::move(*source));
    for (const ProcessPlan &process : module.processes) {
      auto header = detail::generateProcessHeader(plan, process);
      if (!header)
        return header.takeError();
      auto source = detail::generateProcessSource(plan, process);
      if (!source)
        return source.takeError();
      bundle.files.push_back(std::move(*header));
      bundle.files.push_back(std::move(*source));
    }
  }
  std::sort(bundle.files.begin(), bundle.files.end(),
            [](const GeneratedFile &left, const GeneratedFile &right) {
              return left.relativePath < right.relativePath;
            });
  if (auto error = embedSourceBundleFingerprint(bundle))
    return std::move(error);
  if (auto error = validateSourceBundle(plan, bundle))
    return std::move(error);
  return bundle;
}

llvm::Error validateSourceBundle(const ModelPlan &plan,
                                 const SourceBundle &bundle) {
  static constexpr std::array<llvm::StringLiteral, 14> forbiddenTokens = {
      "Python",
      "pybind",
      "dlopen",
      "co_await",
      "std::function",
      "dynamic_cast",
      "runtime_factory",
      "descriptor_interpreter",
      "schema_walker",
      "schema_catalog",
      "catalog_walker",
      "catalog_lookup",
      "topology_mutation",
      "topology_builder"};
  const std::vector<std::string> required = expectedPaths(plan);
  if (!isValidFingerprint(bundle.sourceFingerprint) ||
      !isValidFingerprint(bundle.buildFingerprint))
    return generatorError("ACLOWER-FINGERPRINT",
                          "source bundle build fingerprint is invalid");
  if (bundle.files.size() != required.size())
    return generatorError("ACLOWER-FINGERPRINT",
                          "source bundle has an incomplete file set");
  for (size_t index = 0; index < bundle.files.size(); ++index) {
    const GeneratedFile &file = bundle.files[index];
    if (file.relativePath != required[index] ||
        !isNormalizedRelativePath(file.relativePath))
      return generatorError("ACLOWER-FINGERPRINT",
                            "source paths are not canonical and complete");
    if (file.fingerprint != computeFingerprint(file.content) ||
        file.content.find('\r') != std::string::npos)
      return generatorError("ACLOWER-FINGERPRINT",
                            "source content fingerprint is invalid");
    for (llvm::StringRef token : forbiddenTokens)
      if (llvm::StringRef(file.content).contains(token))
        return generatorError("ACLOWER-UNSUPPORTED-CONSTRUCT",
                              "generated source contains forbidden token '" +
                                  token + "'");
  }
  std::vector<GeneratedFile> preimageFiles = bundle.files;
  size_t embeddedIdentityCount = 0;
  for (GeneratedFile &file : preimageFiles) {
    size_t position = file.content.find(bundle.buildFingerprint);
    while (position != std::string::npos) {
      file.content.replace(position, bundle.buildFingerprint.size(),
                           kGeneratedFingerprintPlaceholder);
      ++embeddedIdentityCount;
      position = file.content.find(bundle.buildFingerprint, position + 1);
    }
  }
  if (embeddedIdentityCount != 1)
    return generatorError("ACLOWER-FINGERPRINT",
                          "source bundle embedded identity is incomplete");
  auto expectedFingerprint = sourceBundleFingerprint(preimageFiles);
  if (!expectedFingerprint || *expectedFingerprint != bundle.sourceFingerprint)
    return generatorError("ACLOWER-FINGERPRINT",
                          "source bundle identity does not match its content");
  return llvm::Error::success();
}

} // namespace acir::codegen
