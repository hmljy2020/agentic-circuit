// RUN: rm -rf %t.first %t.second %t.frozen %t.acsim
// RUN: %acir_opt_public --verify-each=false --pass-pipeline='builtin.module(ac-freeze-topology)' %source_root/test/Conversion/native-event-queue.mlir -o %t.frozen
// RUN: %acir_opt_public --ac-lower-to-acsim --ac-binding-profile=fast --ac-binding-target=x86_64-linux-gnu %t.frozen -o %t.acsim
// RUN: for out in %t.first %t.second; do %acir_cxxgen %t.acsim --frozen-acir=%t.frozen --stop-after=compile --output-root=$out --project-name=native-events --project-identity=project.native-events --system-name=soc --system-identity=system.soc --profile=fast --compiler=%cxx --standard-library=libstdc++ --abi-mode=default --object-format=elf --contract-flag=-std=c++20 --include-root=%source_root/include || exit 1; done
// RUN: diff -r %t.first %t.second
// RUN: grep -R "gfsim::TimedEventQueue<std::int32_t>" %t.first/include/generated/modules
// RUN: grep -R "\.trySchedule(v0, epoch, v1)" %t.first/src/generated/processes
// RUN: grep -R "\.tryRecv(epoch)" %t.first/src/generated/processes
// RUN: grep -R "ProcessWakeKind::EventQueue, queue.id()" %t.first/include/generated/processes
// RUN: grep -R "setEventQueueCapacity(1026)" %t.first/src/generated/model.cpp
// RUN: %not grep -R -E "provider|binding_lock|extern_wrapper" %t.first/include %t.first/src

// The native queue is owned by the generated module and captured by reference
// by producer and consumer processes.  No external binding surface is emitted.
