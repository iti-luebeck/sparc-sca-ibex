// Copyright 2022 Flavien Solt, ETH Zurich.
// Licensed under the General Public License, Version 3.0, see LICENSE for details.
// SPDX-License-Identifier: GPL-3.0-only
//
// Taint-only variant: CellIFT taint propagation without the power-leakage
// counter ports (hamming_weight_counter_t0, hamming_distance_counter_t0,
// leakage_counter_t0).  Used for benchmarking the HD/HW counter overhead in
// isolation.  Generated with TRACK_POWER_LEAKAGE=0 in the Yosys pass.

module ibex_tiny_soc #(
    parameter int unsigned NumTaints = 1,

    // The two below must be equal.
    parameter int unsigned InstrMemDepth = 1 << 15, // 32-bit words
    parameter int unsigned DataMemDepth = 1 << 15, // 32-bit words


    // Derived parameters
    localparam int unsigned InstrMemAw = $clog2(InstrMemDepth),
    localparam int unsigned DataMemAw = $clog2(DataMemDepth)
) (
  input logic clk_i,
  input logic rst_ni,

  input logic [1:0] esc_tx_i,

  input  logic [31:0] hart_id_i,
  input  logic [31:0] boot_addr_i
);
  typedef logic [31:0] data_t;
  typedef logic [31:0] strb_t; // The strobe is bitwise.
  typedef logic [InstrMemAw-1:0] addr_t;

  ///////////////////
  // Ibex instance //
  ///////////////////

  logic clk_esc;
  logic rst_esc;
  logic test_en;
  prim_ram_1p_pkg::ram_1p_cfg_t ram_cfg;
  logic [31:0] hart_id;
  logic [31:0] boot_addr;
  logic irq_software;
  logic irq_timer;
  logic irq_external;
  prim_esc_pkg::esc_tx_t esc_tx;
  prim_esc_pkg::esc_rx_t esc_rx;
  logic debug_req;
  ibex_pkg::crash_dump_t crash_dump;
  lc_ctrl_pkg::lc_tx_t lc_cpu_en;
  logic core_sleep;

  assign clk_esc = '0;
  assign rst_esc = '0;
  assign test_en = '0;
  assign ram_cfg = '0;
  assign hart_id = hart_id_i;
  assign boot_addr = boot_addr_i;
  assign irq_software = '0;
  assign irq_timer = '0;
  assign irq_external = '0;
  assign esc_tx = '0;
  assign debug_req = '0;
  assign lc_cpu_en = lc_ctrl_pkg::On;

  logic  instr_mem_req;
  logic  instr_mem_gnt;
  addr_t instr_mem_addr;
  data_t instr_mem_wdata;
  strb_t instr_mem_strb;
  logic  instr_mem_we;
  data_t instr_mem_rdata;

  logic  data_mem_req;
  logic  data_mem_gnt;
  addr_t data_mem_addr;
  data_t data_mem_wdata;
  strb_t data_mem_strb;
  logic  data_mem_we;
  data_t data_mem_rdata;

  //
  // Wires to follow
  //

  logic core_sleep_o_t0;
  logic [127:0] crash_dump_o_t0;
  logic [17:0] data_mem_addr_o_t0;
  logic data_mem_req_o_t0;
  logic [31:0] data_mem_strb_o_t0;
  logic [31:0] data_mem_wdata_o_t0;
  logic data_mem_we_o_t0;
  logic [1:0] esc_rx_o_t0;
  logic [17:0] instr_mem_addr_o_t0;
  logic instr_mem_req_o_t0;
  logic [31:0] instr_mem_strb_o_t0;
  logic [31:0] instr_mem_wdata_o_t0;
  logic instr_mem_we_o_t0;

  // Input taints (from memory)

  data_t instr_mem_rdata_t0;
  data_t data_mem_rdata_t0;

  cellift_rv_core_ibex_mem_top i_cellift_rv_core_ibex_mem_top (
    // Regular signals
    .clk_i,
    .rst_ni,
    .clk_esc_i             (clk_esc),
    .rst_esc_ni            (rst_esc),
    .test_en_i             (test_en),
    .ram_cfg_i             (ram_cfg),
    .hart_id_i             (hart_id),
    .boot_addr_i           (boot_addr),
    // Instruction memory interface
    .instr_mem_req_o       (instr_mem_req),
    .instr_mem_gnt_i       (instr_mem_gnt),
    .instr_mem_addr_o      (instr_mem_addr),
    .instr_mem_wdata_o     (instr_mem_wdata),
    .instr_mem_strb_o      (instr_mem_strb),
    .instr_mem_we_o        (instr_mem_we),
    .instr_mem_rdata_i     (instr_mem_rdata),
    // Data memory interface
    .data_mem_req_o        (data_mem_req),
    .data_mem_gnt_i        (data_mem_gnt),
    .data_mem_addr_o       (data_mem_addr),
    .data_mem_wdata_o      (data_mem_wdata),
    .data_mem_strb_o       (data_mem_strb),
    .data_mem_we_o         (data_mem_we),
    .data_mem_rdata_i      (data_mem_rdata),
    // Interrupt inputs
    .irq_software_i        (irq_software),
    .irq_timer_i           (irq_timer),
    .irq_external_i        (irq_external),
    // Escalation input for NMI
    .esc_tx_i              (esc_tx_i),
    .esc_rx_o              (esc_rx_o),
    // Debug Interface
    .debug_req_i           (debug_req),
    // Crash dump information
    .crash_dump_o          (crash_dump),

    .lc_cpu_en_i           (lc_cpu_en),
    .core_sleep_o          (core_sleep),

    // Input taints
    .instr_mem_rdata_i_t0 (instr_mem_rdata_t0),
    .data_mem_rdata_i_t0  (data_mem_rdata_t0),

    .core_sleep_o_t0  (core_sleep_o_t0),
    .crash_dump_o_t0  (crash_dump_o_t0),
    .data_mem_addr_o_t0  (data_mem_addr_o_t0),
    .data_mem_req_o_t0  (data_mem_req_o_t0),
    .data_mem_strb_o_t0  (data_mem_strb_o_t0),
    .data_mem_wdata_o_t0  (data_mem_wdata_o_t0),
    .data_mem_we_o_t0  (data_mem_we_o_t0),
    .esc_rx_o_t0  (esc_rx_o_t0),
    .instr_mem_addr_o_t0  (instr_mem_addr_o_t0),
    .instr_mem_req_o_t0  (instr_mem_req_o_t0),
    .instr_mem_strb_o_t0  (instr_mem_strb_o_t0),
    .instr_mem_wdata_o_t0  (instr_mem_wdata_o_t0),
    .instr_mem_we_o_t0  (instr_mem_we_o_t0),

    .rst_esc_ni_t0('0),
    .instr_mem_gnt_i_t0('0),
    .ram_cfg_i_t0('0),
    .clk_esc_i_t0('0),
    .lc_cpu_en_i_t0('0),
    .irq_timer_i_t0('0),
    .hart_id_i_t0('0),
    .irq_external_i_t0('0),
    .irq_software_i_t0('0),
    .boot_addr_i_t0('0),
    .debug_req_i_t0('0),
    .test_en_i_t0('0),
    .data_mem_gnt_i_t0('0),
    .esc_tx_i_t0('0)
  );

  //////////////////////////////
  // Instruction ROM instance //
  //////////////////////////////

  taint_rom #(
    .AddrOffset(32'h0),
    .ROM_ADDR_WIDTH(15),
    .Width(32),
    .ByteAddressed(1'b0),
    .NumTaints(NumTaints)
  ) i_instr_rom (
    .clk_i,
    .rst_ni,
    .test_mode_i(1'b0),
    .init_ni(1'b1),
    .csn(~instr_mem_req),
    .wen(instr_mem_we),
    .be(instr_mem_strb),
    .id(4'b0),
    .add(instr_mem_addr), // 32-bit words
    .wdata(instr_mem_wdata),
    .rdata(instr_mem_rdata),

    .clk_i_t0(1'b0),
    .rst_ni_t0(1'b0),
    .test_mode_i_t0(1'b0),
    .init_ni_t0(1'b0),
    .wdata_t0(instr_mem_wdata_o_t0),
    .add_t0(instr_mem_addr_o_t0),
    .csn_t0(instr_mem_req_o_t0),
    .wen_t0(instr_mem_we_o_t0),
    .be_t0(instr_mem_strb_o_t0),
    .id_t0(4'b0),
    .rdata_t0(instr_mem_rdata_t0)
  );

  assign instr_mem_gnt = '1;

  ////////////////////////
  // Data SRAM instance //
  ////////////////////////

  ift_sram_mem #(
    .Width(32),
    .Depth(DataMemDepth),
    .NumTaints(NumTaints),
  ) i_data_sram (
    .clk_i,
    .rst_ni,

    .req_i(data_mem_req),
    .write_i(data_mem_we),
    .addr_i(data_mem_addr), // 32-bit words
    .wdata_i(data_mem_wdata),
    .wmask_i(data_mem_strb),
    .rdata_o(data_mem_rdata),

    .req_i_taint(data_mem_req_o_t0),
    .write_i_taint(data_mem_we_o_t0),
    .addr_i_taint(data_mem_addr_o_t0),
    .wdata_i_taint(data_mem_wdata_o_t0),
    .wmask_i_taint(data_mem_strb_o_t0),
    .rdata_o_taint(data_mem_rdata_t0)
  );

  assign data_mem_gnt = '1;

endmodule
