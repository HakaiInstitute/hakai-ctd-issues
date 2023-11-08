import json
from pathlib import Path
import pandas as pd
from hakai_api import Client
import plotly.express as px


client = Client()
CTD_CASTS_FIELDS = [
    "organization",
    "work_area",
    "station",
    "device_model",
    "hakai_id",
    "process_error",
]

ISSUE_TEMPLATE = """
---
name: Tracking issue
about: Use this template for tracking new features.
title: {process_error_message}
labels: {organization},{work_area}
assignees: 
---

## issue
The Hakai CTD Processing tool encountered the following problem which is affecting {N_hakai_id} hakai_ids:
{process_error_message}

!!! notes
    {process_error}


!!! hakai_ids
    {hakai_ids}
"""


def get_errors():
    def _get_error_message(error):
        try:
            error = json.loads(error)["message"]
            if error.startswith("No lat/long information available for station "):
                return "Unknown reference station position"
            return f'"{error}"'
        except:
            return f'"{error}"'

    response = client.get(
        f"{client.api_root}/ctd/views/file/cast?"
        + f"process_error!=null&process_error!=''&limit=-1&fields={','.join(CTD_CASTS_FIELDS)}"
    )
    response.raise_for_status()
    df = pd.DataFrame(response.json())
    df["process_error_message"] = df["process_error"].apply(_get_error_message)
    return df


def main(output="ctd-issues.html"):
    def _get_subset(items, max_items=4):
        if isinstance(items, (list, pd.Series)):
            items = list(items)
            if len(items) > max_items:
                items = items[:max_items]
                items += ['...']
            return items
        return items
    
    def _get_issue_md(issue):
        return ISSUE_TEMPLATE.format(**issue.to_dict())

    errors = get_errors()

    # Group errors
    summarized_errors = errors.groupby(["organization", "work_area", "process_error_message"]).agg(
        {
            "hakai_id": [_get_subset, "count"],
            "process_error": "first",
            "station": list,
        }
    )
    summarized_errors.columns = ["hakai_ids", "N_hakai_id", "process_error", "stations"]
    summarized_errors = summarized_errors.sort_values(
        ["organization", "N_hakai_id"], ascending=False
    )
    summarized_errors = summarized_errors.reset_index()
    summarized_errors['issues_md'] = summarized_errors.apply(_get_issue_md,axis=1)
    # Load existing github issues

    # Drop already existing ones

    # Generate github new issues
    fig = px.sunburst(summarized_errors,path=["organization",'work_area','process_error_message'], color='N_hakai_id')
    Path("sumburs.html").write_text(fig.to_html())
    summarized_errors.to_html(output)
    for id, issue in summarized_errors.iterrows():
        (Path("issues")/ f"issue-{id}.md").write_text(issue['issues_md'])



if __name__ == "__main__":
    main()
