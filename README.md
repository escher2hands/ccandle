# ccandle
Confluence toolset to shine light on the quality and navigability of technical documentation

<img src="docs/images/light_in_cave.png" width="700" alt="Overview">

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
- run `ccandle overview` to get at-a-glance appraisal of quality and navigability metrics in your tracked Confluence spaces
- dive deeper with `ccandle stats` to find specific information on most popular (linked-to) pages, orphans, duplicate pages, or more
- run `ccandle sql query YOUR_QUERY` to run arbitrary queries on your processed offline page mirror
- run `ccandle labels add LABEL_NAME PAGE_ID_LIST` to add labels to a bulk set of pages, and 
`... delete LABEL_NAME PAGE_ID_LIST` to remove. 

Is that it? For now, it is! This is a rebuild I am making on my own time. In the next four weeks, I plan to introduce some 
stronger features:

## roadmap
- Link and label suggestions (via fancy embeddings and statistical methods)

## more to-dos:
- reach feature parity with my company's internal tool (gap explorer, space content distribution explorer,...)