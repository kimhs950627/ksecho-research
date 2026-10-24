#!/usr/bin/env python3
"""
segment_map.py — 벽운동 eyeball 보조 프로토타입

ED/ES 심내막 경계에서 구역별 내향 변위 지수를 계산해 6구역 지도로 낸다.
  1) 마스크에서 경계를 뽑고 중심·심첨축을 정한다
  2) 중심에서 방사 방향으로 반경 프로파일 r(θ)을 만든다 (ED, ES)
  3) 심첨 기준 각도 φ로 3밴드(첨부·중간·기저) × 2벽(중격·측벽) = 6구역
  4) 구역 지수 = 평균 (r_ED − r_ES) / LV 길이
  5) 정상 분포 대비 z 점수 → 임계 이하를 '주의'로 표시

실행:
  python3 segment_map.py --demo        # 합성 데이터로 전체 파이프라인 확인
  python3 segment_map.py --camus-dir /path/to/camus/training --case patient0001
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

SEGMENTS = [
    ("basal_septal", "기저 중격"),
    ("mid_septal", "중간 중격"),
    ("apical_septal", "첨부 중격"),
    ("basal_lateral", "기저 측벽"),
    ("mid_lateral", "중간 측벽"),
    ("apical_lateral", "첨부 측벽"),
]

# ── 데모용 정상 기준 분포 (실제 연구에서는 정상 EF 코호트에서 계산) ──
DEMO_REFERENCE = {
    "basal_septal":    (0.16, 0.045),
    "mid_septal":      (0.20, 0.050),
    "apical_septal":   (0.14, 0.045),
    "basal_lateral":   (0.17, 0.045),
    "mid_lateral":     (0.21, 0.050),
    "apical_lateral":  (0.15, 0.045),
}


# ────────────────────────────── 기하 ──────────────────────────────
def radial_profile(mask: np.ndarray, center: tuple[float, float], n_theta: int = 240):
    """중심에서 방사 방향으로 나가며 마지막으로 마스크에 닿는 거리 r(θ)."""
    h, w = mask.shape
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    radius = np.zeros(n_theta, dtype=float)
    step = 0.5
    for i, t in enumerate(theta):
        dx, dy = math.cos(t), math.sin(t)
        r = 0.0
        last = 0.0
        while True:
            r += step
            x = center[0] + dx * r
            y = center[1] + dy * r
            if x < 0 or y < 0 or x >= w - 1 or y >= h - 1:
                break
            if mask[int(round(y)), int(round(x))]:
                last = r
        radius[i] = last
    return theta, radius


def apex_axis(mask: np.ndarray, center: tuple[float, float], theta: np.ndarray, radius: np.ndarray):
    """중심에서 가장 먼 방향을 심첨축으로 잡는다."""
    k = int(np.argmax(radius))
    return theta[k]


def segment_angles(theta: np.ndarray, apex: float):
    """심첨 기준 부호 있는 각도 φ ∈ [-π, π]."""
    phi = (theta - apex + math.pi) % (2.0 * math.pi) - math.pi
    return phi


def assign_segments(phi: np.ndarray, raw: np.ndarray) -> dict[str, float]:
    """|φ| 3분할(첨부/중간/기저) × 부호(중격/측벽). 각 구역의 평균 원시값."""
    a = np.abs(phi)
    band = np.where(a < math.pi / 3, "apical", np.where(a < 2 * math.pi / 3, "mid", "basal"))
    wall = np.where(phi >= 0, "septal", "lateral")   # 필요 시 --septum-side 로 뒤집기
    out: dict[str, list[float]] = {}
    for b, wl, v in zip(band, wall, raw):
        out.setdefault(f"{b}_{wl}", []).append(float(v))
    return {k: float(np.mean(v)) for k, v in out.items()}


def compute(cavity_ed: np.ndarray, cavity_es: np.ndarray, septum_side: str = "positive"):
    ys, xs = np.nonzero(cavity_ed)
    center = (float(xs.mean()), float(ys.mean()))
    th, r_ed = radial_profile(cavity_ed, center)
    _, r_es = radial_profile(cavity_es, center)
    apex = apex_axis(cavity_ed, center, th, r_ed)
    lv_length = float(r_ed.max() + r_es.max()) / 2.0     # 심첨–기저 근사 길이
    phi = segment_angles(th, apex)
    if septum_side == "negative":
        phi = -phi
    idx = (r_ed - r_es) / max(lv_length, 1e-6)
    return {
        "center": center,
        "apex_angle": float(apex),
        "lv_length": lv_length,
        "segments": assign_segments(phi, idx),
        "profile": {"theta": th.tolist(), "r_ed": r_ed.tolist(), "r_es": r_es.tolist()},
    }


def zscore(segments: dict[str, float], reference: dict[str, tuple[float, float]]):
    rows = []
    for key, label in SEGMENTS:
        value = segments.get(key)
        ref = reference.get(key)
        if value is None or ref is None:
            rows.append({"segment": key, "label": label, "index": None, "z": None, "flag": "no-data"})
            continue
        mean, sd = ref
        z = (value - mean) / sd if sd > 0 else 0.0
        rows.append({"segment": key, "label": label, "index": value, "z": z,
                     "flag": "주의" if z <= -2.0 else "정상"})
    return rows


# ────────────────────────────── 데모 ──────────────────────────────
def synthetic_pair(size: int = 256, impaired: str = "mid_septal"):
    """정상 좌심실 유사 형상(첨부는 뾰족, 기저는 판막면으로 절단) + 한 구역만 수축이 둔한 쌍."""
    yy, xx = np.mgrid[0:size, 0:size]
    cx = size * 0.50
    cy = size * 0.55
    a, b = 46.0, 82.0
    annulus_y = cy + 0.72 * b             # 승모판면(수평 절단)
    theta = np.arctan2(yy - cy, xx - cx)
    apex = -math.pi / 2                    # 심첨은 위쪽
    phi = (theta - apex + math.pi) % (2 * math.pi) - math.pi
    band = np.where(np.abs(phi) < math.pi / 3, "apical",
                    np.where(np.abs(phi) < 2 * math.pi / 3, "mid", "basal"))
    wall = np.where(phi >= 0, "septal", "lateral")

    def cavity(rate_normal: float, rate_impaired: float) -> np.ndarray:
        shrink = np.full(phi.shape, rate_normal)
        shrink[(band == impaired.split("_")[0]) & (wall == impaired.split("_")[1])] = rate_impaired
        r = ((xx - cx) / a) ** 2 + ((yy - cy) / b) ** 2 <= (1 - shrink) ** 2
        return (r & (yy <= annulus_y)).astype(np.uint8)

    return cavity(0.0, 0.0), cavity(0.22, 0.04), impaired


def plot(ed, es, result, rows, out_png: Path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    th = np.array(result["profile"]["theta"])
    r_ed = np.array(result["profile"]["r_ed"])
    r_es = np.array(result["profile"]["r_es"])
    cx, cy = result["center"]

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2), gridspec_kw={"width_ratios": [1, 1.15]})
    ax = axes[0]
    ax.imshow(ed + es * 2, cmap="Greys", alpha=.55)
    ax.plot(cx + r_ed * np.cos(th), cy + r_ed * np.sin(th), lw=1.0, color="#0E7490", label="ED")
    ax.plot(cx + r_es * np.cos(th), cy + r_es * np.sin(th), lw=1.0, color="#B45309", label="ES")
    ax.plot(cx, cy, "+", color="#0F171C", ms=9)
    ax.set_title("ED / ES endocardial border", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([]); ax.legend(fontsize=7, loc="lower right", frameon=False)

    ax2 = axes[1]
    zs = [(r["z"] if r["z"] is not None else 0.0) for r in rows]
    names = [r["segment"].replace("_", " ") for r in rows]
    colors = ["#9E2B2B" if r["flag"] == "주의" else "#0E7490" for r in rows]
    ax2.barh(names, zs, color=colors, height=.62)
    ax2.axvline(-2.0, color="#9E2B2B", ls="--", lw=1)
    ax2.axvline(0, color="#3B4A51", lw=.8)
    ax2.set_xlim(-4.6, 2.6)
    ax2.set_xlabel("z-score vs normal  (left = hypokinetic)", fontsize=9)
    ax2.invert_yaxis()
    ax2.tick_params(labelsize=8)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    fig.suptitle(title, fontsize=10, x=.02, ha="left")
    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    plt.close(fig)


# ────────────────────────────── CAMUS ──────────────────────────────
def load_camus(camus_dir: Path, case: str):
    """CAMUS: patientXXXX_info.cfg (EDN/ESN) + *_ED_contours.mhd / *_ES_contours.mhd.
    라벨: 1=LV 심내막, 2=LV 심외막, 3=좌심방. SimpleITK 필요."""
    import SimpleITK as sitk

    info = camus_dir / f"{case}_info.cfg"
    edn = esn = None
    if info.exists():
        for line in info.read_text().splitlines():
            if line.startswith("EDN:"):
                edn = int(line.split(":")[1])
            if line.startswith("ESN:"):
                esn = int(line.split(":")[1])
    if edn is None or esn is None:
        raise SystemExit(f"{info} 에서 EDN/ESN 을 찾지 못했습니다")

    def cavity(tag, frame):
        img = sitk.ReadImage(str(camus_dir / f"{case}_{tag}_contours.mhd"))
        arr = sitk.GetArrayFromImage(img)          # (T, H, W)
        return (arr[frame] == 1).astype(np.uint8)  # 1 = 심내막

    return cavity("ED", edn), cavity("ES", esn), f"{case} · ED frame {edn} / ES frame {esn}"


# ────────────────────────────── main ──────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="합성 데이터로 실행")
    ap.add_argument("--camus-dir", type=Path, help="CAMUS training 디렉터리")
    ap.add_argument("--case", default="patient0001")
    ap.add_argument("--septum-side", choices=["positive", "negative"], default="positive")
    ap.add_argument("--impaired", default="mid_septal", help="데모: 둔하게 만들 구역")
    ap.add_argument("--outdir", type=Path, default=Path("out"))
    args = ap.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    if args.demo:
        ed, es, impaired = synthetic_pair(impaired=args.impaired)
        title = f"DEMO · synthetic hypokinesis = {impaired}"
    elif args.camus_dir:
        ed, es, title = load_camus(args.camus_dir, args.case)
    else:
        raise SystemExit("--demo 또는 --camus-dir 중 하나가 필요합니다")

    result = compute(ed, es, septum_side=args.septum_side)
    rows = zscore(result["segments"], DEMO_REFERENCE)

    tag = "demo" if args.demo else args.case
    with (args.outdir / f"{tag}_segments.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["segment", "label", "index", "z", "flag"])
        w.writeheader()
        for r in rows:
            w.writerow({k: ("—" if v is None else (round(v, 4) if isinstance(v, float) else v))
                        for k, v in r.items()})
    (args.outdir / f"{tag}_result.json").write_text(json.dumps(
        {k: v for k, v in result.items() if k != "profile"}, ensure_ascii=False, indent=2))
    plot(ed, es, result, rows, args.outdir / f"{tag}_map.png", title)

    print(f"{'구역':<14}{'지수':>8}{'z':>8}  판정")
    for r in rows:
        idx = "—" if r["index"] is None else f"{r['index']:.3f}"
        z = "—" if r["z"] is None else f"{r['z']:+.2f}"
        print(f"{r['label']:<14}{idx:>8}{z:>8}  {r['flag']}")
    flagged = [r["label"] for r in rows if r["flag"] == "주의"]
    print(f"\n주의 구역 {len(flagged)}개" + (f": {', '.join(flagged)}" if flagged else ""))
    print(f"저장: {args.outdir}/{tag}_map.png · {tag}_segments.csv")


if __name__ == "__main__":
    main()
