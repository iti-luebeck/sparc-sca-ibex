// Ibex CellIFT Per-Cycle CSV Logger
// Drives the simulation tick-by-tick and writes the three leakage counters to
// a CSV file at every clock cycle, matching the standalone Proteus TVLA flow.

#include "testbench.h"
#include "ticks.h"

#include <cstdlib>
#include <fstream>
#include <iostream>

int main(int argc, char **argv, char **env) {
  Verilated::commandArgs(argc, argv);
  Verilated::traceEverOn(VM_TRACE);

  const char *csvfile_env = std::getenv("CSVFILE");
  if (!csvfile_env) {
    std::cerr << "CSVFILE environment variable not set." << std::endl;
    return 1;
  }

  std::cout << "Starting CellIFT CSV logger." << std::endl;

  int simlen = get_sim_length_cycles(LEADTICKS);

  Testbench *tb = new Testbench(cl_get_tracefile());
  tb->reset();

  // Ibex toplevel requires these inputs to be initialized for clean boot.
  tb->module_->hart_id_i = 0;
  tb->module_->boot_addr_i = 0;

  std::ofstream csv(csvfile_env);
  if (!csv.is_open()) {
    std::cerr << "Cannot open CSVFILE: " << csvfile_env << std::endl;
    delete tb;
    return 1;
  }

  csv << "cycle,leakage_counter_t0,hamming_weight_counter_t0,hamming_distance_counter_t0\n";

  for (int cycle = 0; cycle < simlen; cycle++) {
    tb->tick(1);

#ifndef IS_VANILLA
    csv << cycle << ","
  << tb->module_->leakage_counter_t0 << ","
  << tb->module_->hamming_weight_counter_t0 << ","
  << tb->module_->hamming_distance_counter_t0 << "\n";
#else
    csv << cycle << ",0,0,0\n";
#endif
  }

  csv.close();

  std::cout << "Testbench CSV complete. Cycles logged: " << simlen << std::endl;
  std::cout << "CSV written to " << csvfile_env << std::endl;

#ifndef IS_VANILLA
  std::cout << "=== CellIFT Leakage Counters ===" << std::endl;
  std::cout << "leakage_counter_t0:          " << std::dec
            << tb->module_->leakage_counter_t0 << std::endl;
  std::cout << "hamming_weight_counter_t0:   " << std::dec
            << tb->module_->hamming_weight_counter_t0 << std::endl;
  std::cout << "hamming_distance_counter_t0: " << std::dec
            << tb->module_->hamming_distance_counter_t0 << std::endl;
#endif

  delete tb;
  return 0;
}
