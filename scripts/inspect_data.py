
from datasets import load_dataset
import pandas as pd

try:
    print("Loading dataset ahmedheakl/resume-atlas...")
    dataset = load_dataset("ahmedheakl/resume-atlas")
    df = dataset['train'].to_pandas()
    
    print(f"Columns: {df.columns.tolist()}")
    print("First row:")
    print(df.iloc[0].to_dict())
                
except Exception as e:
    print(f"Error: {e}")
