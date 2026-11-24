# AeroDesign Power Board Rev3: bench characterization

![Bench setup: KORAD KA3005P supply, RIGOL DHO804, DIY DC load on its heat-pipe tower, power board with probe bodge wires](images/bench_setup.jpg)

This board powered UBC AeroDesign's 2025 competition aircraft. It takes a 2S to 4S LiPo (7 to 22 V) and makes a
protected 5 V servo rail rated at 15 A, with power-good flags and a servo current-sense output for the flight
controller. It flew all season without bench data. This campaign (November 2026) is its first full bench
characterization: what it does, how close it is to its design, and where its limits are.

| What | Where |
|---|---|
| Schematic (PDF) | [`docs/PowerBoard_Rev3_schematic.pdf`](docs/PowerBoard_Rev3_schematic.pdf) |
| Test log (every step, limit, verdict and note) | [`bench_test/PowerBoard_Rev3_BenchTest_Log.xlsx`](bench_test/PowerBoard_Rev3_BenchTest_Log.xlsx) |
| Original DVT/EOL test plan | [`bench_test/AeroDesign_PowerBoard_DVT_EOL_Test_Plan.xlsx`](bench_test/AeroDesign_PowerBoard_DVT_EOL_Test_Plan.xlsx) |
| Instrument layer (PSU, scope, load, safety monitor) | [`bench_test/tools/bench_lib.py`](bench_test/tools/bench_lib.py) |
| Raw data and scope captures | [`bench_test/results/`](bench_test/results), [`bench_test/scope/`](bench_test/scope) |
| Scope captures, labelled and annotated (all 35) | [`bench_test/scope_annotated/`](bench_test/scope_annotated) |
| Probe and bodge-wire map | [`bench_test/probe_point_map.png`](bench_test/probe_point_map.png) |

**Bench:**
- **KORAD KA3005P** (30 V / 5 A): the supply.
- **RIGOL DHO804** (70 MHz, 12-bit): the waveforms.
- **Brymen BM235:** DC reference.
- **DIY DC load** ([dc-electronic-load](https://github.com/WeymenKoo/dc-electronic-load)): the load.

Everything is driven from Python, with each test scripted and logged.

**The load tops out at 1.9 A,** so every output measurement here covers 0 to 1.9 A of the board's 15 A rating.
The short-circuit test goes far beyond that. What is still untested is listed at the end.

## The circuit

![Power path: battery -> input eFuse -> LM5146 buck -> servo eFuse -> servos / FC](images/sch_top_blocks.png)

**Input protection (U4 TPS25983 + Q4 P-FET).**
- **Reverse polarity:** blocked by Q4.
- **Input TVS:** D23 (SMCJ24CA, bidirectional).
- **Undervoltage lockout:** turns on at 5.97 V, off at 5.48 V.
- **Over-voltage cut-off:** off at 24.86 V, back on at 22.79 V.
- **Current limit:** 17.81 A, latched.

![Input eFuse](images/sch_input_efuse.png)

**Buck (U3 LM5146, Q2/Q3 AON7534, L1 3.3 µH, 300 kHz).**
- 4.994 V set point, 4 ms soft-start.
- Feedback taken at VBUCK_OUT, *before* the servo eFuse.
- Diode emulation at light load.

![Buck](images/sch_buck_lm5146.png)

**Servo output eFuse and current sense.**
- **eFuse:** U1 TPS25983 with Q1 as a back-to-back blocking FET.
  - 17.81 A limit, 4 retries at 94 ms, over-voltage cut-off at 7.93 V.
- **Current sense:** R1 (5 mΩ) and U2 INA240A2 give SRV_Isns.
  - Mid-supply referenced: its zero-current output is half of 5V_PROT.
  - It goes to the flight controller's ADC.

![Servo eFuse and current sense](images/sch_servo_efuse_isense.png)

## Measured specification

| Parameter | Design | Measured |
|---|---|---|
| Input UVLO on / off | 5.97 / 5.48 V | **5.97-5.995 / 5.53-5.55 V** |
| Input over-voltage off / back on | 24.86 / 22.79 V | **24.92-24.95 / 23.03-23.05 V** (auto-recovers) |
| Reverse polarity, -22 V | blocked | **< 10 µA** |
| Output, no load | 4.994 V | **5.055-5.063 V**, line regulation **5 mV** over 7.4-22 V |
| No-load input current | – | **16-19 mA** (0.19-0.40 W) |
| Load regulation, 0 → 1.9 A | – | buck node **3-6 mV**, servo headers **≈ 50 mV** (23.5 mΩ path) |
| Efficiency at 1.9 A | – | **94.4 / 93.8 / 92.4 / 91.0 %** at 7.4 / 12 / 16.8 / 22 V |
| Switching frequency | 300 kHz | **308.8 kHz**, fixed at every load (DCM ≤ 1 A, CCM at 1.9 A) |
| Soft-start | 4 ms | **2.95 ms** (10-90 %), ≈ 3.7 ms 0 → 5 V, 9 mV overshoot |
| Output ripple, 5V_PROT at 1.9 A | 8 mV | **14-15 mVpp** fundamental, 15-16 mVpp total |
| Load step, 1.55 A | – | **67-172 mV** dip, 160-430 µs to ±10 mV, well damped |
| Switch-node peak, 22 V / 1.9 A | < 27 V | **23.4 V** (a minimum: 70 MHz scope) |
| Current-sense sensitivity | 0.10 V/A | **0.251 V/A** |
| Servo short circuit | limit, 4 retries at 94 ms, latch | trips in **< 0.1 ms**, **5 retries** (first after ≈ 40 ms, then ≈ 85 ms apart), latches, power-cycle recovers |
| Hot-plug VIN peak at 7.4 / 12 / 16.8 V | – | **11.6 / 19.7 / 30.5 V** |

## Test cases

Every scope capture below is the raw screenshot with a title, the test conditions, a channel legend (signal, probe point, scale) and call-outs. The originals are in [`bench_test/scope/`](bench_test/scope). Where the same run was also logged as data, its Python plot sits next to the capture.


### 1. Input protection thresholds
**Method:** the supply is stepped 20 mV at a time with a 0.5 A load. VIN is measured at the board, and the
input eFuse power-good flag marks the switching point. For reverse polarity, the supply leads are swapped and a
meter in series measures the current.

**Result:**
- Every threshold is within about 1 % of design.
- The buck starts the moment U4 turns on: its own UVLO divider sits lower, so it never limits.
- The over-voltage cut-off recovers by itself, with about 1.9 V of hysteresis.
- At -22 V nothing conducts: Q4 blocks, and D23 is bidirectional.

| Input UVLO turn-on with 0.5 A load: clean, no chatter | Over-voltage trip at 24.9 V |
|---|---|
| ![B2.1 UVLO turn-on, annotated scope capture](bench_test/scope_annotated/B2.1_uvlo_rise.png) | ![B2.5 over-voltage trip, annotated scope capture](bench_test/scope_annotated/B2.5_ovp_trip.png) |
| **UVLO turn-off** | **Over-voltage recovery at 23.0 V** |
| ![B2.3 UVLO turn-off, annotated scope capture](bench_test/scope_annotated/B2.3_uvlo_fall.png) | ![B2.6 over-voltage recovery, annotated scope capture](bench_test/scope_annotated/B2.6_ovp_recover.png) |

### 2. Start-up and power sequencing
**Method:** power is applied with a hand-touched + lead (ground fixed), as a battery plug-in would apply it.
All four rails are captured.

**Result:**
- **Soft-start:** the buck starts 3.6 ms after power, with a 2.95 ms ramp and 9 mV overshoot.
- **Servo eFuse:** connects the rail only once the buck is up, ramping at **2.5 V/ms** whether loaded or not.
  - Into about 200 µF that is about 0.5 A of inrush (1.01 A designed).
- **Power-good order:** buck power-good at 6.8 ms, 5V_PROT ≥ 4.75 V at 9.25 ms, OPGD at 10.95 ms.
- **Start-up into a 1.9 A load:** the rail is good at **9.3 ms (22 V) and 10.3 ms (7.4 V)**, with no restart.
  - At 7.4 V the input sags to 6.75 V, still 1.2 V above the UVLO turn-off.

| Scope: 12 V, no load (annotated) | Logged data, same run |
|---|---|
| ![B3.4 start-up at 12 V, annotated scope capture](bench_test/scope_annotated/B3.4_12V_0A_opgd.png) | ![Start-up at 12 V, Python plot](images/startup.png) |

Start-up into 1.9 A at 7.4 V, the worst case: [`B3.5_7V4_1A9_r2.png`](bench_test/scope_annotated/B3.5_7V4_1A9_r2.png).

### 3. Hot-plug overshoot
**Method:** a live supply is touched onto the input, sampled at 3.2 ns with full bandwidth and no load.

**Result:** the supply leads (about 0.9 µH) charge C38 (1 µF) through Q4's body diode in a 3 µs LC half-cycle.
- **The peak:** 1.56-1.81× VIN.
- **Where it lands:** Q4's body diode then blocks reverse current, so the peak stays on U4's input, and the leads ring at about 2 MHz against D23.
- **At 16.8 V (4S full charge):** VIN reaches **30.5 V**, on 30 V-rated parts. U4 is still off at that instant, so the buck FETs are not exposed.

| Scope: 16.8 V hot-plug (annotated) | Logged data, all three voltages |
|---|---|
| ![B3.6 hot-plug at 16.8 V, annotated scope capture](bench_test/scope_annotated/B3.6_hotplug_16.8V.png) | ![Hot-plug overshoot, Python plot](images/hotplug.png) |

### 4. Switch node
**Result:**
- **Frequency:** fixed at about 310 kHz from 0 A to 1.9 A, with no pulse skipping.
  - Up to 1 A it runs in discontinuous mode with diode emulation (the node rings around 5 V between pulses).
  - At 1.9 A it is continuous.
- **The changeover** matches the 3.3 µH inductor's ≈ 2.9 A peak-to-peak ripple at 12 V in.
- **Edge stress at 22 V:** the edge peaks at **23.4 V**, a 22 % margin to the 30 V FETs, and undershoots to -2.0 V (dead time).

| 22 V, 1.9 A rising edge (1.25 GSa/s) | 22 V, 1.9 A falling edge (1.25 GSa/s) |
|---|---|
| ![B3.8 rising edge, annotated scope capture](bench_test/scope_annotated/B3.8_sw_rise_22V_1A9_1G25.png) | ![B3.8 falling edge, annotated scope capture](bench_test/scope_annotated/B3.8_sw_fall_22V_1A9_1G25.png) |
| **12 V, 1.9 A: continuous, 308.8 kHz** | **12 V, no load: diode emulation** |
| ![B3.7 switch-node frequency, annotated scope capture](bench_test/scope_annotated/B3.7_sw_freq_12V_1A9.png) | ![B3.9 switch node at no load, annotated scope capture](bench_test/scope_annotated/B3.9_sw_12V_0.0A.png) |

### 5. Efficiency and regulation
**Method:** automatic sweep: 4 input voltages × 11 loads (0-1.9 A). Rails come from scope means, anchored to DMM
readings at 0 A. Output current comes from the load's readback, and input current from the supply.

**Result:**
- **Efficiency:** 91-94 % at 1.9 A, measured to the servo headers, so it includes the eFuse and shunt losses.
- **The buck regulates its own node to within about 5 mV.**
- **The servo rail droops 50 mV** because the feedback is taken *before* U1 + Q1 + R1 + copper.
  - That path measures **23.5 mΩ**: about **0.35 V and 5 W at the 15 A rating**.

![Efficiency](images/efficiency.png)
![Regulation](images/regulation.png)
![Servo path drop](images/servo_path_drop.png)

### 6. Ripple
**Method:** 1× probe with a ground spring across the output capacitor, 20 MHz bandwidth, laptop on battery to break
the ground loop. The noise floor was 2.5 mVpp.

**Result:**
- **5V_PROT:** **14.0 mVpp** fundamental at 16.8 V and 15.4 mVpp at 22 V, all at 1.9 A, against an 8 mV target.
- **Why it misses the target:** the 2 × 100 µF 16 V X5R output capacitors keep only about half their capacitance at 5 V.
  - 3.55 A of inductor ripple into about 112 µF predicts 13 mV.
- **On the buck side of U1** (5 × 4.7 µF only), the ripple is **57 mVpp**.
- **Input ripple:** 122 mVpp (ceramic capacitors only).

| 5V_PROT, 16.8 V / 1.9 A | VBUCK_OUT, 22 V / 1.9 A |
|---|---|
| ![B3.10 5V_PROT ripple, annotated scope capture](bench_test/scope_annotated/B3.10_vsrv_ripple_16V8_1A9.png) | ![B3.13 VBUCK_OUT ripple, annotated scope capture](bench_test/scope_annotated/B3.13_vbuck_ripple_22V_1A9.png) |
| **Probe noise floor** | **Input ripple, 16.8 V / 1.9 A** |
| ![B3.1 noise floor, annotated scope capture](bench_test/scope_annotated/B3.1_noisefloor.png) | ![B3.14 input ripple, annotated scope capture](bench_test/scope_annotated/B3.14_vin_ripple_16V8_1A9.png) |

### 7. Load step
**Method:** the load's built-in square wave steps between 0.1 and 1.8 A (about 1.55 A), with edges of about 10 µs.
The scope averages 16 captures.

**Result:**
- **Response:** one dip and a smooth recovery. At 7.4 V the release also shows one small (≈ 18 mV) undershoot, but there is no sustained ringing, so the loop is stable and well damped.
- **Dip size:** **172 / 121 / 67 mV** at 7.4 / 16.8 / 22 V. It is largest at low VIN, where the inductor current can only ramp at (VIN - VOUT)/L ≈ 0.7 A/µs.
- **Recovery:** 160-430 µs, slower than a 50 kHz crossover would give, so the loop is likely conservatively compensated.

| Scope: 7.4 V, 0.1 → 1.8 A (annotated) | Logged data, all six steps |
|---|---|
| ![B3.19 load step at 7.4 V, annotated scope capture](bench_test/scope_annotated/B3.19_loadstep_7.4V_load.png) | ![Load step, Python plot](images/loadstep.png) |

The other five steps: [`bench_test/scope_annotated/`](bench_test/scope_annotated/) (`B3.19_loadstep_*`).

### 8. Servo current sense
**Result:**
- **Sensitivity:** SRV_Isns measures **0.251 V/A**, linear to ±18 mA, with its zero at half of 5V_PROT (+0-2 mV).
- **The part is right:** U2 is marked I240A2, and **the INA240A2 is a 50 V/V part** (A1 = 20, A2 = 50, A3 = 100, A4 = 200 V/V).
- **R1 measures 5.01 mΩ,** and its Kelvin routing is correct: the INA sees exactly R1's drop.
- **So the build matches the parts.** The schematic note's "A2 = 20 V/V" is wrong.

**Consequences:**
- **SRV_Isns passes the flight controller ADC's 3.3 V full scale at about 3.2 A.**
- **It saturates near 5 V at about 9.8 A,** so the 15 A rating cannot be measured.

![Current sense](images/current_sense.png)

### 9. Servo output short circuit
**Method:** a hard short from J2 pin 2 (5V_PROT) to pin 3 (PGND) at 22 V, with no load.

**Result:**
- **U1 trips at once** through its fast-trip path, rather than the 2 ms blanking used for overloads.
- **It retries 5 times, then latches off.** The first retry comes after about 40 ms, the rest about 85 ms apart. A power-cycle recovers the board, with no damage.
- **Each trip causes a load dump on VBUCK_OUT.** The inductor's stored energy (≈ ½ · 3.3 µH · 17.8 A² ≈ 0.5 mJ) has nowhere to go but C17-C21 (5 × 4.7 µF).
  - Read off run 2's capture (5 V/div, ±0.3 V): VBUCK_OUT jumps to **≈ 9.3 V on the first trip** and **9.6 to 11.3 V on the five retries**.
  - Every one is above U1's 7.93 V over-voltage threshold, and **4 of the 5 retries go above the 10 V rating of C17-C21**.
- **Two runs, and why both are shown:**
  - Run 1 had VBUCK_OUT at 2 V/div. It went off the top of the screen, so its logged data flat-tops at 8.74 V. That is the scope's range, not the peak.
  - Run 2 repeated the test at 5 V/div. Its waveform download failed (it saved only 20 ms before the trigger), so its screenshot is the record of the peaks.

![B4.6 run 2: short circuit at 22 V, CH2 at 5 V/div, annotated scope capture](bench_test/scope_annotated/B4.6_short_22V_full_r2.png)

Run 1, the logged data with the clipping marked ([raw capture](bench_test/scope_annotated/B4.6_short_22V_full.png)):

![B4.6 run 1: logged data, VBUCK_OUT clipped at 8.74 V](bench_test/scope/B4.6_short_analysis.png)

## Findings

| ID | Severity | Finding |
|---|---|---|
| F1 | **Major** | Hot-plug overshoot of 1.8× VIN: a 4S plug-in puts **30.5 V** on U4's input and 30 V parts. The D23 clamp (≈ 27-39 V) does not protect them. |
| F2 | **Major** | Load dump on VBUCK_OUT at every servo eFuse trip: **up to ≈ 11.3 V on 10 V-rated C17-C21** (4 of 5 retries above 10 V), above U1's 7.93 V over-voltage threshold. Too little buck-side capacitance. |
| F3 | **Major** | Current sense is 0.25 V/A (INA240A2 = 50 V/V; the design assumed 20 V/V). The FC ADC clips at **≈ 3.2 A** and sees > 3.3 V above that; the output saturates at ≈ 9.8 A. |
| F4 | Moderate | 23.5 mΩ servo path after the feedback point: 50 mV droop at 1.9 A, about **0.35 V and 5 W at 15 A**. |
| F5 | Minor | 5V_PROT ripple 14-15 mVpp against an 8 mV target, caused by capacitor DC-bias loss. |
| F6 | Minor | Slow but well-damped load-step recovery (160-430 µs); 172 mV dip at 7.4 V. |
| F7 | Minor | IPGD is pulled up from 5V_PROT, so it can't indicate "input good" until the whole chain is up. BKPGD is a 7.5 V logic level. |
| F8 | Info | Input ripple is 122 mVpp with ceramic-only input capacitors, the same root cause as F1. |
| ✔ | – | All protection thresholds within about 1 % of design. Reverse polarity blocked. 91-94 % efficiency. Clean sequencing. Stable loop. Short circuit survived and latched as designed. |

## Not tested (needs more than a 1.9 A load)
- Regulation, efficiency, ripple and switch-node stress from 2 to 15 A.
- The 17.81 A current-limit level and the 2 ms overload blanking.
- The buck's own current limit.
- A 15 A thermal soak.
- Input inrush with a sense resistor.
- A real LiPo plug-in with the flight harness.

## Corrective actions and Rev B plan

**For the flown Rev3 board (rework and firmware):**
1. **Current sense (F3).**
   - Firmware: use **I = (SRV_Isns - V(5V_PROT)/2) / 0.25 V/A**, with a fixed-zero error of about 0.1 A at 1.9 A otherwise.
   - Add a resistor divider in front of the FC ADC, so SRV_Isns can never drive the pin above 3.3 V.
   - Or swap U2 to an INA240A1.
2. **VBUCK_OUT bulk capacitor (F2).** Add ≥ 47 µF (16-25 V polymer) at the VBUCK_OUT pad next to L1, and replace C17-C21 with 16 V-rated parts.
3. **Input damping (F1).** Add ≥ 100 µF, 35 V low-ESR electrolytic or polymer across the input. Then re-measure the 4S hot-plug.
4. **Fix the schematic note** for U2 (INA240A2 = 50 V/V) and the related design documentation.

**Rev B design changes:**

| Area | Change | Addresses |
|---|---|---|
| Input | Bulk damping capacitor; TVS with a lower clamp (≈ 20 V stand-off) and/or 40 V-rated eFuse and FETs | F1, F8 |
| Buck output | ≥ 47 µF bulk before U1, 16-25 V MLCCs; optional clamp below 10 V | F2 |
| Current sense | INA240A1 (20 V/V) with REF1 = REF2 = GND: unidirectional 0-15 A → 0-1.5 V, fits a 3.3 V ADC | F3 |
| Regulation | Remote-sense the buck feedback at 5V_PROT (with a local fallback), and/or cut path resistance (lower-Rds Q1, wider copper) | F4 |
| Output capacitors | 25 V-rated or larger-case 100 µF parts, or more capacitance, to meet the 8 mV target | F5 |
| Control loop | Measure the loop gain and retune compensation (R15, C44, C46, C47) toward the 50 kHz target | F6 |
| Power-good | Pull IPGD up to an always-present rail; level-shift BKPGD if it's ever used | F7 |
| Validation | Load bank or higher-current load to finish the 2-15 A, current-limit, thermal and LiPo hot-plug tests | Not tested |
