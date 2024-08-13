# hakai-ctd-issues
Public facing repo to handle the different issues encountered while processing Hakai CTD data. 


## Development

Clone repository

``` shell
git clone https://github.com/HakaiInstitute/hakai-ctd-issues
```

Copy `sample.env` as `.env` and include Hakai API token.

Install environement
```shell
poetry install
```

Build page
```shell
poetry run hakai_ctd_issues
```

Build page with mkdocs
```
poetry run mkdocs serve 
```