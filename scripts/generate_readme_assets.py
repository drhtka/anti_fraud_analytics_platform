from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "assets" / "readme"


def ensure_assets_dir() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def generate_scoring_scenarios_chart() -> None:
    scenarios = ["Low risk", "Medium-ish", "High risk"]
    scores = [0.430693, 0.667183, 0.885149]
    colors = ["#0f766e", "#d97706", "#dc2626"]
    threshold = 0.7

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(scenarios, scores, color=colors, width=0.58)
    ax.axhline(
        threshold,
        color="#475569",
        linestyle="--",
        linewidth=1.6,
        label="Manual review threshold",
    )
    ax.set_title("Fraud Score by Transaction Scenario", fontsize=14, weight="bold")
    ax.set_ylabel("Fraud score")
    ax.set_ylim(0, 1.0)
    ax.grid(axis="y", linestyle=":", alpha=0.35)
    ax.set_axisbelow(True)

    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            score + 0.02,
            f"{score:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
            weight="bold",
        )

    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(ASSETS_DIR / "scoring-scenarios.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def generate_signal_profile_chart() -> None:
    scenarios = ["Low risk", "Medium-ish", "High risk"]
    signal_counts = [0, 3, 5]
    manual_review = [0, 0, 1]
    colors = ["#cbd5e1", "#93c5fd", "#fca5a5"]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(scenarios, signal_counts, color=colors, height=0.55)
    ax.set_title("Risk Signal Density by Scenario", fontsize=14, weight="bold")
    ax.set_xlabel("Number of active risk signals")
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.set_axisbelow(True)

    for bar, signal_count, needs_review in zip(bars, signal_counts, manual_review):
        label = f"{signal_count} signals"
        if needs_review:
            label += " | manual review"
        ax.text(
            signal_count + 0.08,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            fontsize=10,
            weight="bold" if needs_review else "normal",
            color="#0f172a",
        )

    ax.set_xlim(0, 6.4)
    fig.tight_layout()
    fig.savefig(ASSETS_DIR / "risk-signal-profile.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ensure_assets_dir()
    generate_scoring_scenarios_chart()
    generate_signal_profile_chart()


if __name__ == "__main__":
    main()
