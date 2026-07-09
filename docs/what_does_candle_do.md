# ccandle gives you tools to manage larger Confluence spaces, or webs of spaces

## 'overview' feature

<img src="docs/images/overview_sample.jpg" width="500" alt="Overview">

After scraping and processing your tracked Confluence spaces (`ccandle sync`), ccandle can 
generate an overview of your space quality across three dimensions:
- topology / connectedness
- page quality
- use of advanced navigational elements

### Why not measure content quality?
Well, without burning a lot of compute on a fancy LLM, measuring the content quality is 
just impossible for any reasonable deterministic algorithm. Even if you could throw around 
the compute to chuck a few hundred or thousand or tens of thousands of pages (yes, some 
teams rely on that much technical documentation) you'd need to give that LLM context about 
the project. Probably, that context comes from...the documentation you're processing. 
Perhaps some future developer can tackle this issue. However, due to these difficulties, 
ccandle focuses on *form* and not content. 

## Managing labels
Gotta document the document machine...please wait...

## Managing navboxes
Gotta document the document machine...please wait...