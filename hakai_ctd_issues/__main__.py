import json
import re
from pathlib import Path

import click
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from hakai_api import Client
from jinja2 import Environment, FileSystemLoader
from loguru import logger

load_dotenv(".env")

environment = Environment(loader=FileSystemLoader("hakai_ctd_issues/templates/"))


client = Client()
site = Path("site")
issues_path = Path("issues")
CTD_CASTS_FIELDS = [
    "organization",
    "work_area","cruise",
    "station",
    "device_model",
    "cast_type",
    "hakai_id",
    "process_error",
]
ORGANIZATION_LABELS = {
    "hakai": "Hakai Institute",
    "nature_trust": "Nature Trust",
    "sfc": "Skeena Fisheries Commission",
    "parks_canada": "Parks Canada",
}

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
                return "Unknown reference station"
            return f'"{error}"'.replace('\n',' ')
        except:
            if len(error) > 300:
                error = error[:300]

            return f'"{error}"'

    response = client.get(
        f"{client.api_root}/ctd/views/file/cast?"
        + f"process_error!=null&process_error!=''&limit=-1&fields={','.join(CTD_CASTS_FIELDS)}"
    )
    response.raise_for_status()
    errors = pd.DataFrame(response.json())
    errors["process_error_message"] = errors["process_error"].apply(_get_error_message).str.replace('\n',' ')
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

    errors["work_area"] = errors.apply(
        lambda x: f"{x['work_area']}[cruise={x['cruise']}]"
        if x["organization"] == "NATURE TRUST"
        else x["work_area"],
        axis=1,
    )
    summarized_errors = errors.groupby(
        ["organization", "work_area", "cast_type", "process_error_message"]
    ).agg(
        {
            "hakai_id": [_get_subset, "count"],
            "process_error": "first",
            "station": set,
        }
    )
    summarized_errors.columns = ["hakai_ids", "count", "process_error", "stations"]
    summarized_errors = summarized_errors.sort_values(
        ["organization", "count"], ascending=False
    )
    return summarized_errors.reset_index()


@click.command()
@click.option(
    "--output",
    default=Path("docs"),
    help="Output directory",
    type=click.Path(file_okay=False, dir_okay=True),
)
def main(output="output"):
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
    logger.info(f"Found {len(errors)} errors")
    summarized_errors = get_summarized_errors(errors)
    summarized_errors["process_error_message_short"] = summarized_errors[
        "process_error_message"
    ].apply(lambda x: re.sub('[\{"\]', "", x.split(".")[0]) if x else x)
    summarized_errors["issues_md"] = summarized_errors.apply(_get_issue_md, axis=1)
    logger.info(f"Summarized into {len(summarized_errors)} errors")

    # Load existing github issues

    # Compare already existing ones

    # Close resolved issues

    # Update existing issues

    # Generate directories if doesn't exist
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    issues_folder = output / "issues"
    issues_folder.mkdir(parents=True, exist_ok=True)

    # for id, issue in summarized_errors.iterrows():
    #     (issues_folder / f"issue-{id}.md").write_text(issue["issues_md"])

    # Generate summary page per organization
    for organization, df_org in summarized_errors.groupby("organization"):
        organization = organization.replace(" ", "_").lower()
        org_dir = output / organization
        org_dir.mkdir(parents=True, exist_ok=True)

        figure = (
            px.histogram(
                df_org,
                x="process_error_message_short",
                y="count",
                color="work_area",
                pattern_shape="cast_type",
                height=500,
                width=1000,
            )
            .update_layout(xaxis=dict(tickangle=10))
            .update_xaxes(
                tickvals=df_org["process_error_message_short"].unique(),
                ticktext=[
                    label[:45] + "..." if len(label) > 45 else label
                    for label in df_org["process_error_message_short"].unique()
                ],
            )
            
        )

        summary_table = df_org[
            ["work_area", "cast_type", "process_error_message", "count", "hakai_ids"]
        ]

        organization_summary = environment.get_template("issue_summary.md.jinja")
        summary_page = organization_summary.render(
            total_errors=len(df_org),
            affected_hakai_ids=df_org["count"].sum(),
            organization=ORGANIZATION_LABELS.get(organization,organization),
            figure=figure,
            summary_table=summary_table,
        )
        (org_dir / "index.md").write_text(summary_page)


if __name__ == "__main__":
    main()
