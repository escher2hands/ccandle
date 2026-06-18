# ccandle
Confluence toolset to shine light on the quality and navigability of technical documentation

## goals
- CLI tool to sync user local offline db with their Confluence Cloud instance
- processor to strip plain text from HTML, get analytics (word count, page type), and add other useful metadata
- statistical analyzer of spaces, to give visibility on quality and basic dimensions

## getting started
### installation
- run `pip install -r requirements.txt` and `pip install -e .` to install to your IDE
- enter values for `ccandle connection` email, url, and token, so you can connect to your Confluence Cloud instance. 
Note: manage API tokens from Atlassian at: https://id.atlassian.com/manage/api-tokens

### tracking spaces
- run `ccandle spaces list` to find the space id of any spaces you are interested in tracking
- run `ccandle spaces add SPACE_ID ALIAS` to add a space to track 
- run `ccandle sync` to scrape the space, and process the scraped pages

### do things
- run `ccandle sql query YOUR_QUERY` to run arbitrary queries on your processed offline page mirror
- run `ccandle labels add LABEL_NAME PAGE_ID_LIST` to add labels to a bulk set of pages, and 
`... delete LABEL_NAME PAGE_ID_LIST` to remove. 

Is that it? For now, it is! This is a rebuild I am making on my own time. In the next six weeks, I plan to introduce some 
stronger features:

## roadmap
- Overview: get at a glance metrics for Confluence space health on characteristics like space connectedness, 
page quality, and space navigability
- Stats: pull specific information about pages, like finding count and page ids of duplicates, orphans, and other
undesirable junk. Get info on which pages are the most linked to, and more
- Link and label suggestions (via fancy embeddings and statistical methods)

## more to-dos:
- change filepath handling to support running from a terminal as precompiled lib, instead of only within an IDE.
- reach feature parity with my company's internal tool (gap explorer, space content distribution explorer,...)