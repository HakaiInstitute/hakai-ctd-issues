import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
from hakai_api import Client
from jinja2 import Environment, FileSystemLoader

environment = Environment(loader=FileSystemLoader("hakai_ctd_issues/templates/"))


client = Client()
site = Path("site")
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
The Hakai CTD Processing tool encountered the following problem which is affecting {count} hakai_ids:
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
    errors = pd.DataFrame(response.json())
    errors["process_error_message"] = errors["process_error"].apply(_get_error_message)
    return errors


def get_summarized_errors(errors):
    def _get_subset(items, max_items=4):
        if isinstance(items, (list, pd.Series)):
            items = list(items)
            if len(items) > max_items:
                items = items[:max_items]
                items += ["..."]
            return items
        return items

    summarized_errors = errors.groupby(
        ["organization", "work_area", "process_error_message"]
    ).agg(
        {
            "hakai_id": [_get_subset, "count"],
            "process_error": "first",
            "station": list,
        }
    )
    summarized_errors.columns = ["hakai_ids", "count", "process_error", "stations"]
    summarized_errors = summarized_errors.sort_values(
        ["organization", "count"], ascending=False
    )
    return summarized_errors.reset_index()


def main(output="ctd-issues.html"):
    def _get_subset(items, max_items=4):
        if isinstance(items, (list, pd.Series)):
            items = list(items)
            if len(items) > max_items:
                items = items[:max_items]
                items += ["..."]
            return items
        return items

    def _get_issue_md(issue):
        return ISSUE_TEMPLATE.format(**issue.to_dict())

    errors = get_errors()
    summarized_errors = get_summarized_errors(errors)
    summarized_errors["process_error_message_short"] = summarized_errors[
        "process_error_message"
    ].apply(lambda x: re.sub('[\{"\]', "", x.split(".")[0]) if x else x)
    summarized_errors["issues_md"] = summarized_errors.apply(_get_issue_md, axis=1)

    # Load existing github issues

    # Compare already existing ones

    # Close resolved issues

    # Update existing issues

    # Generate github new issues
    if not site.exists():
        site.mkdir(parents=True, exist_ok=True)
    for id, issue in summarized_errors.iterrows():
        (Path("issues") / f"issue-{id}.md").write_text(issue["issues_md"])

    # Generate summary page per organization
    for organization, df_org in summarized_errors.groupby("organization"):
        organization = organization.replace(" ", "_")
        org_dir = site / organization
        org_dir.mkdir(parents=True, exist_ok=True)

        sunburst_figure_html = px.sunburst(
            df_org,
            path=["work_area", "process_error_message_short"],
            values="count",
            color="count",
        ).to_html(full_html=False, include_plotlyjs="cdn")

        summary_table_html = df_org[
            ["work_area", "process_error_message", "count"]
        ].to_html(
            index=False, classes=["table-bordered", "table-striped", "table-hover"]
        )

        organization_summary = environment.get_template("issue_summary.html")
        summary_page = organization_summary.render(
            organization=organization,
            sunburst_figure_html=sunburst_figure_html,
            summary_table_html=summary_table_html,
        )
        (org_dir / "index.html").write_text(summary_page)


if __name__ == "__main__":
    main()
