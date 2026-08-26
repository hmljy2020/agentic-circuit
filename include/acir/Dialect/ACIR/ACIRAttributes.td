#ifndef ACIR_DIALECT_ACIR_ACIRATTRIBUTES_TD
#define ACIR_DIALECT_ACIR_ACIRATTRIBUTES_TD

include "acir/Dialect/ACIR/ACIRDialect.td"
include "mlir/IR/AttrTypeBase.td"
include "mlir/IR/EnumAttr.td"

def ACIR_Unit_Ticks : I32EnumAttrCase<"Ticks", 0, "ticks">;
def ACIR_Unit_Cycles : I32EnumAttrCase<"Cycles", 1, "cycles">;
def ACIR_Unit_Seconds : I32EnumAttrCase<"Seconds", 2, "seconds">;
def ACIR_Unit_Milliseconds
    : I32EnumAttrCase<"Milliseconds", 3, "milliseconds">;
def ACIR_Unit_Microseconds
    : I32EnumAttrCase<"Microseconds", 4, "microseconds">;
def ACIR_Unit_Nanoseconds
    : I32EnumAttrCase<"Nanoseconds", 5, "nanoseconds">;
def ACIR_Unit_Picoseconds
    : I32EnumAttrCase<"Picoseconds", 6, "picoseconds">;
def ACIR_Unit_Bytes : I32EnumAttrCase<"Bytes", 7, "bytes">;
def ACIR_Unit_Bits : I32EnumAttrCase<"Bits", 8, "bits">;
def ACIR_Unit_Entries : I32EnumAttrCase<"Entries", 9, "entries">;
def ACIR_Unit_Packets : I32EnumAttrCase<"Packets", 10, "packets">;
def ACIR_Unit_Transactions
    : I32EnumAttrCase<"Transactions", 11, "transactions">;

def ACIR_Unit : I32EnumAttr<"Unit", "ACIR exact measurement unit", [
  ACIR_Unit_Ticks,
  ACIR_Unit_Cycles,
  ACIR_Unit_Seconds,
  ACIR_Unit_Milliseconds,
  ACIR_Unit_Microseconds,
  ACIR_Unit_Nanoseconds,
  ACIR_Unit_Picoseconds,
  ACIR_Unit_Bytes,
  ACIR_Unit_Bits,
  ACIR_Unit_Entries,
  ACIR_Unit_Packets,
  ACIR_Unit_Transactions
]> {
  let genSpecializedAttr = 0;
  let cppNamespace = "::acir::ac";
}

def ACIR_QueueOrdering_FIFO
    : I32EnumAttrCase<"FIFO", 0, "fifo">;

def ACIR_QueueOrdering
    : I32EnumAttr<"QueueOrdering", "ACIR Queue ordering", [
        ACIR_QueueOrdering_FIFO
      ]> {
  let genSpecializedAttr = 0;
  let cppNamespace = "::acir::ac";
}

def ACIR_QueueContractAttr
    : AttrDef<ACIR_Dialect, "QueueContract"> {
  let mnemonic = "queue_contract";
  let parameters = (ins "int64_t":$depth,
                        "int64_t":$latency,
                        "int64_t":$rate,
                        "mlir::FlatSymbolRefAttr":$domain,
                        EnumParameter<ACIR_QueueOrdering>:$ordering);
  let assemblyFormat = [{
    `<` `depth` `=` $depth `,` `latency` `=` $latency `,`
        `rate` `=` $rate `,` `domain` `=` $domain `,`
        `ordering` `=` $ordering `>`
  }];
  let genVerifyDecl = 1;
}

#endif // ACIR_DIALECT_ACIR_ACIRATTRIBUTES_TD
