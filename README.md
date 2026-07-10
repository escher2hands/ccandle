# ccandle
Confluence toolset to shine light on the quality and navigability of technical documentation.

<img src="docs/images/light_in_cave.png" width="700" alt="Overview">

## goals
- CLI tool to sync user local offline db with their Confluence Cloud instance
- processor to strip plain text from HTML, get analytics (word count, page type), and add 
other useful metadata
- statistical analyzer of spaces, to give visibility on quality and basic dimensions

A toolset for [Confluence power users](docs/who_is_this_for.md) to coax their Confluence 
pages to be more [findable and maintainable](docs/an_ideal_confluence.md). See also some 
info on [how it works](docs/how_does_ccandle_work.md). 

## getting started
### installation
- run `pip install -r requirements.txt` and `pip install -e .` to install to your IDE
- enter values for `ccandle connection` email, url, and token, so you can connect to your 
Confluence Cloud instance. 
Note: manage API tokens from Atlassian at: https://id.atlassian.com/manage/api-tokens

### tracking spaces
- run `ccandle spaces list` to find the space id of any spaces you are interested in tracking
- run `ccandle spaces add SPACE_ID ALIAS` to add a space to track 
- run `ccandle sync` to scrape the space, and process the scraped pages

### do things
- run `ccandle overview` to get at-a-glance appraisal of quality and navigability metrics 
in your tracked Confluence spaces
- dive deeper with `ccandle stats` to find specific information on most popular (linked-to) 
pages, orphans, duplicate pages, and more
- run `ccandle sql query YOUR_QUERY` to run arbitrary queries on your processed offline page 
mirror
- run `ccandle labels add LABEL_NAME PAGE_ID_LIST` to add labels to a bulk set of pages, and 
`... remove LABEL_NAME PAGE_ID_LIST` to remove
- run `ccandle excerpts add SOURCE_PAGE_ID TO_PAGE_ID_LIST` to add navbox excerpts to a bulk 
set of pages, and `... remove PAGE_ID_LIST` to remove

See more info on the [brief features overview](docs/what_does_ccandle_do.md).
Is that it? For now, it is! This is a rebuild I am making on my own time. In the next few 
weeks, I plan to introduce some stronger features:

## roadmap
- Link and label suggestions (via fancy embeddings and statistical methods)
- Gap explorer (find topics mentioned across pages, but for which no authoritative page 
exists)
- Space content distribution explorer (find parts of the page tree with unexpectedly dense 
documentation, and filter out those parts with mostly template and blank pages)
