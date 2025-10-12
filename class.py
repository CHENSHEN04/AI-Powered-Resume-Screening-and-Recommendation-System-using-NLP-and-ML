from datasets import load_dataset
from typing import List, Dict
import pandas as pd
from tqdm import tqdm

def load_resume_data(local_cache_dir: str = None):
    ds_id = "MikePfunk28/resume-training-dataset"
    print(f"Loading dataset {ds_id} from Hugging Face...")

    raw_ds = load_dataset(ds_id, split='train')

    rows = []
    for ex in tqdm(raw_ds, desc="Processing records"):
        if 'role' in ex and 'context' in ex:
            rows.append({
                'role': ex['role'],
                'content': ex['content']
            })
        else:
            for k in ['messages', 'conversations', 'content']:
                if k in ex:
                    val = ex[k]
                        # if val is a list of messages
                    if isinstance(val, list):
                        for msg in val:
                            rows.append({'role': msg.get('role'), 'content': msg.get('content')})
                    else:
                        rows.append({'role': 'unknown', 'content': str(val)})
                    break
    else:
        rows.append({'role': 'unknown', 'content': str(ex)})

    df = pd.DataFrame(rows)
    return df

def extract_user_resumes(df):
    """
    From the conversations DataFrame, extract user messages which likely contain the resume text.
    Returns a DataFrame with 'resume_text' column.
    """
    user_df = df[df['role'] == 'user'].copy()
    user_df = user_df.reset_index(drop=True)
    user_df = user_df.rename(columns={'content': 'resume_text'})
    return user_df[['resume_text']]

if __name__ == "__main__":
    df = load_resume_data()
    resumes = extract_user_resumes(df)
    print("Extracted resumes:", len(resumes))
    print(resumes.head(3))