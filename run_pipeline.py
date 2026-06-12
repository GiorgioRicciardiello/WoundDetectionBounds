#!/usr/bin/env python
"""Run the pipeline with experiments.xlsx"""

from library.pipeline import Pipeline
import sys

def main():
    try:
        print("\n" + "="*80)
        print("RUNNING WOUND HEALING PIPELINE WITH experiments.xlsx")
        print("="*80)

        pipeline = Pipeline('config.yaml')

        print("\n[INFO] Starting segmentation...")
        print(f"[INFO] Input file: {pipeline.config.input_excel}")
        print(f"[INFO] Output dir: {pipeline.output_base}")
        print(f"[INFO] Workers: {pipeline.config.segmentation.n_workers}")
        print(f"[INFO] Kalman filter: {pipeline.config.segmentation.use_kalman}")

        # Run segmentation only
        results = pipeline.run(stages=["segmentation"])

        print("\n" + "="*80)
        print("SEGMENTATION COMPLETE")
        print("="*80)
        if results:
            if 'trajectories' in results:
                print(f"✓ Trajectories: {len(results['trajectories'])} objects")
            if 'measurements' in results:
                print(f"✓ Measurements: {len(results['measurements'])} rows")
                if 'wound_area' in results['measurements'].columns:
                    print(f"  Mean wound area: {results['measurements']['wound_area'].mean():.1f} px")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"Message: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
