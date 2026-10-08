import sys
from pathlib import Path
sys.path.insert(0, 'C:/Projects/Quantumattack/src')
import pandas as pd
from quantumattack.features import compute_features
from quantumattack.feature_config import FeatureConfig

chunk_file, out_dir = sys.argv[1], Path(sys.argv[2])
ids = [l for l in Path(chunk_file).read_text().splitlines() if l]
cfg = FeatureConfig()
for sid in ids:
    df = pd.read_parquet(f'C:/Projects/Quantumattack/data/phase3/{sid}.parquet')
    feat = compute_features(df, cfg)
    feat.to_parquet(out_dir / f'{sid}.parquet', index=False)
print(f'worker {Path(chunk_file).name}: {len(ids)} done')
