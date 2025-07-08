import pandas as pd

# Ensure DataFrames are converted to JSON-serializable structures
def convert_df_fields(result):
    if "loan_metrics" in result:
        metrics = result["loan_metrics"]
        for key, val in metrics.items():
            if isinstance(val, pd.DataFrame):
                metrics[key] = val.to_dict(orient="records" if val.shape[0] > 1 else "index")
    return result