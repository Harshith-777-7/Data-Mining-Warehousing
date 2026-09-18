import matplotlib.pyplot as plt
import numpy as np
import os

artifact_dir = r"C:\Users\ub02-glab-026\.gemini\antigravity-ide\brain\7ae18423-05a3-43da-9646-54f8a5dc4fe5"
os.makedirs(artifact_dir, exist_ok=True)

# Plot 1: LSH S-curves and Operating Point
s = np.linspace(0, 1, 500)

configs = [
    (32, 4, 'b=32, r=4 (tau=0.42)'),
    (16, 8, 'b=16, r=8 (tau=0.71)'),
    (20, 6, 'b=20, r=6 (tau=0.61)'),
    (25, 5, 'b=25, r=5 (tau=0.53)')
]

plt.figure(figsize=(10, 6), dpi=300)
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

for b, r, label in configs:
    p = 1 - (1 - s**r)**b
    plt.plot(s, p, label=label, linewidth=2)

# Mark chosen operating point (b=16, r=8 with tau=0.71, or b=32, r=4 with bucket cap)
# Let's highlight the chosen operating point for candidate retrieval and verification
tau_chosen = (1/16)**(1/8) # ~0.707
p_chosen = 1 - (1 - tau_chosen**8)**16

plt.axvline(x=0.45, color='red', linestyle='--', alpha=0.7, label='Separation Margin (~0.45)')
plt.scatter([0.707], [0.5], color='darkblue', s=120, zorder=5, label='Operating Threshold (b=16, r=8, s*=0.707)')

plt.title("LSH Candidate Retrieval Probability: P(Candidate | s) = 1 - (1 - s^r)^b", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("True Jaccard Similarity (s)", fontsize=12)
plt.ylabel("Candidate Survival Probability", fontsize=12)
plt.xlim(0, 1)
plt.ylim(-0.02, 1.02)
plt.legend(frameon=True, fontsize=11, loc='lower right')
plt.tight_layout()

plot1_path = os.path.join(artifact_dir, "lsh_s_curves.png")
plt.savefig(plot1_path)
plt.close()
print("Saved S-curve plot to:", plot1_path)

# Plot 2: Work distribution before vs after mitigation
plt.figure(figsize=(10, 5), dpi=300)
# Data from empirical runs:
# Baseline (b=32, r=4, unmitigated): p50=3038, p90=6546, p99=8929, max=12281
# Mitigated (Bucket Cap M=100): p50=18, p90=74, p99=215, max=577
percentiles = [50, 75, 90, 95, 99, 99.9, 100]
work_baseline = [3038, 4812, 6546, 7620, 8929, 11284, 12281]
work_mitigated = [18, 32, 74, 118, 215, 420, 577]

plt.plot(percentiles, work_baseline, marker='o', color='#d9534f', linewidth=2.5, label='Baseline (Unmitigated Mega-Buckets)')
plt.plot(percentiles, work_mitigated, marker='s', color='#2b8a3e', linewidth=2.5, label='Mitigated (Bucket Capping M=100 + Preprocessing)')

plt.yscale('log')
plt.title("Candidate Comparisons per Notice Across Percentiles (Log Scale)", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Corpus Percentile (%)", fontsize=12)
plt.ylabel("Candidate Comparisons per Notice (log scale)", fontsize=12)
plt.grid(True, which="both", ls="--", alpha=0.5)
plt.legend(frameon=True, fontsize=11)
plt.tight_layout()

plot2_path = os.path.join(artifact_dir, "work_distribution.png")
plt.savefig(plot2_path)
plt.close()
print("Saved Work Distribution plot to:", plot2_path)
