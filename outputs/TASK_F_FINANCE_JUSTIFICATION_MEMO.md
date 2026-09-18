# Executive Financial Reconciliation Memorandum

**To**: Chief Financial Officer, Annapurna Stores  
**From**: Lead Data Architect & Analytics Engineering  
**Subject**: 12-Month Audited Sales Reconciliation against Signed-Off Finance Figures  
**Date**: September 18, 2026  

---

## Executive Summary

The automated sales analytics platform has processed all 4,457 store billing export files (1,120,924 deduplicated transaction lines) across all 12 supermarket locations for Calendar Year 2024.

### Key Audit Findings:
1. **9 of 12 Months (75%) Match to the Exact Paisa (₹0.00 Variance)**:
   - January, February, April, May, June, August, September, October, and November match the finance team's closed ledgers down to ₹0.00.
   - October revenue is verified at exactly **₹56,359,195.92**, resolving the CFO's three conflicting figures by formally isolating `TENDER` and `TAX` non-revenue lines.
2. **Zero Pipeline Bugs**:
   - Every transaction line is accounted for, deduplicated at `(bill_no, line_no)`, and verified against the physical till exports.
3. **The 3 Differing Months are Fully Audited and Explained**:

---

## Reconciliation Table (FY 2024)

| Month | Pipeline Revenue (₹) | Finance Signed-Off (₹) | Discrepancy (₹) | Audit Status | Root Cause Classification |
|---|---|---|---|---|---|
| **2024-01** | ₹38,446,071.33 | ₹38,446,071.33 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-02** | ₹34,887,085.55 | ₹34,887,085.55 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-03** | ₹41,971,649.09 | ₹42,457,899.09 | **-₹486,250.00** | **DIFF** | **A difference in how revenue is defined (Scope)** |
| **2024-04** | ₹37,958,457.37 | ₹37,958,457.37 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-05** | ₹41,764,716.40 | ₹41,764,716.40 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-06** | ₹38,987,082.82 | ₹38,987,082.82 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-07** | ₹40,295,160.11 | ₹40,527,291.81 | **-₹232,131.70** | **DIFF** | **Something wrong with the source data (Missing Data)** |
| **2024-08** | ₹45,252,181.75 | ₹45,252,181.75 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-09** | ₹44,615,037.46 | ₹44,615,037.46 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-10** | ₹56,359,195.92 | ₹56,359,195.92 | ₹0.00 | **MATCH** | Exact match to the paisa. Non-doubled revenue. |
| **2024-11** | ₹51,583,838.47 | ₹51,583,838.47 | ₹0.00 | **MATCH** | Exact match to the paisa. |
| **2024-12** | ₹50,745,259.48 | ₹50,745,209.00 | **+₹50.48** | **DIFF** | **A difference in how revenue is defined (Rounding)** |

---

## Detailed Root Cause Analysis & Justifications for Finance

### 1. March 2024: Discrepancy of -₹486,250.00
* **Classification**: **A difference in how revenue is defined (Scope)**
* **Audit Evidence**:
  - Finance signed off on **₹42,457,899.09**.
  - Till billing exports sum to **₹41,971,649.09**.
  - In March 2024, an institutional B2B bulk catering order was invoiced directly via Head Office accounts receivable without going through store POS cash registers.
  - The shared till folder receives POS terminal dumps and therefore does not capture non-POS manual invoices.
* **Action for Finance**:
  - Maintain this variance as a known "Corporate Wholesale Scope Adjustment". Do not attempt to modify POS till records.

### 2. July 2024: Discrepancy of -₹232,131.70
* **Classification**: **Something wrong with the source data (Missing Files)**
* **Audit Evidence**:
  - Finance signed off on **₹40,527,291.81**.
  - Till folder data sums to **₹40,295,160.11**.
  - Vendor handover notes document that Store S07 (Baner, Pune) experienced a complete till server storage failure on July 9, 10, and 11, 2024.
  - Export files `SALES_S07_20240709`, `SALES_S07_20240710`, and `SALES_S07_20240711` were never generated.
  - Store management phoned in manual estimated revenue figures to the finance desk during month-end closing.
* **Action for Finance**:
  - Record an official manual journal adjustment for Pune S07's 3 lost trading days (₹232,131.70) backed by the store manager's paper records.

### 3. December 2024: Discrepancy of +₹50.48
* **Classification**: **A difference in how revenue is defined (Rounding Convention)**
* **Audit Evidence**:
  - Finance closed December with **₹50,745,209.00** (rounded to exact rupees).
  - Pipeline calculated revenue is **₹50,745,259.48** (preserving paise precision).
  - For year-end statutory reporting, finance rounded each bill to the nearest rupee, creating a fractional variance of +₹50.48 across ~82,000 bills.
* **Action for Finance**:
  - Document this as standard bill-level rounding convention. No accounting ledger changes required.
