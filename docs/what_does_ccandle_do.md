# ccandle gives you tools to manage larger Confluence spaces, or webs of spaces

## measure Confluence quality with a single command

<img src="images/overview_sample.jpg" width="500" alt="Evaluation of a Confluence space">

Run one command: `ccandle overview`, out pops data.

After scraping and processing your tracked Confluence spaces (`ccandle sync`), ccandle can 
generate an overview of your space quality across three dimensions:
- topology / connectedness
- page quality
- use of advanced navigational elements

By deterministically measuring your space quality, you get direct insight into where 
to focus maintenance efforts. You can also benchmark against old evaluations, to see 
if your maintenance efforts are outpacing the 'rot' that Confluence spaces tend towards.

### why not measure content quality?
Well, without burning a lot of compute on a fancy LLM, measuring the content quality is 
just impossible for any reasonable deterministic algorithm. Even if you could throw around 
the compute to chuck a few hundred or thousand or tens of thousands of pages (yes, some 
teams rely on that much technical documentation) you'd need to give that LLM context about 
the project. Probably, that context comes from...the documentation you're processing. Of 
course, this becomes a bootstrapping problem.

Perhaps some future developer can tackle this issue. However, due to the mentioned 
difficulties, ccandle focuses on *form* and not content. 

## taming structure by managing labels and navboxes in bulk
While outdated information and junk pages are a menace, often spaces are most in need 
of a more helpful structure. [Navboxes](an_ideal_confluence.md#wikipedia-style-navboxes-guide-readers-along-a-topic) 
are one structural element we can add to Confluence pages to give more structure; to 
*guide* readers to the next page in a topic. Creating trails requires work--but with 
ccandle, that work is faster:
1. *search* relevant pages in a topic / category is a bit easier with our sql queries (you can 
filter our rich metadata, and of course, ordinary keyword search). Nab their page IDs.
2. *label* pages with `ccandle labels LABEL_NAME PAGE_ID_LIST` in bulk. This updates pages 
via REST API.
3. insert *navboxes* into pages with `ccandle excerpts add NAV_SOURCE_PID TO_PAGE_ID_LIST` 
4. *merge labels* that ought to be combined with `ccandle labels merge FROM_LABEL TO_LABEL`. 
It'll automatically add the new label, remove the old label, and explain any failures 
(usually access issues). Live no more with fragmented searches of meeting-minutes and 
minutes-of-meeting. Merge them all, with one command.

All of this could be done by hand, of course, but who wants to click four times each page 
to apply a label to dozens of pages? Who wants to insert a navbox 'excerpt', then forget 
what the source page was, and what the excerpt's name was? Work smarter, and faster.

<img src="images/labels_screenshot.png" width="500" alt="Screenshot of labels workflow">

## rapidly identify junk -- and kill it before it rots your Confluence
Confluence Cloud doesn't allow deep inspection of space contents. Getting a list of empty 
pages isn't really possible. But leaving empty pages, or duplicate pages, clutters 
your page tree, your search results, and your Confluence.

run `ccandle stats duplicates` to get a list of pages that are functionally identical. 
In many spaces I've encountered, pages are created from a template, are *never* filled 
in, and at most have a date or name changed. With the *duplicates* feature, you can see 
which dupe groups exist, which spaces they belong to, and even set the sensitivity for 
how much is allowed to change for them to be considered duplicates.

<img src="images/duplicates_screenshot.png" width="500" alt="Screenshot of duplicates workflow">

run `ccandle stats empty` to get a list of pages that are, well, empty. Of course, 
pure word count doesn't always tell the full story. So you get to check for *blanks*, 
*wordless*, or *stubs* pages. You even get to preview if they have structural value: 
if they have children and are acting as useful folders, or are really just junk. Filter 
by last modified date if you're really risk avoidant, and kill only those pages so 
ancient no one will even notice they're gone.

<img src="images/empties_screenshot.png" width="500" alt="Screenshot of empties workflow">


## map out important pages (link relevance, tree structure relevance)
<img src="images/cartographer_screenshot.png" width="400" alt="Screenshot of empties workflow">

Some spaces are monsters, with thousands of pages, and a complex, jumbled page tree 
hierarchy. It can be nearly impossible to map out which pages are in these 'monster' 
spaces, let alone to do that quickly. 

Cartographer is a feature to help you map out these spaces. It analyzes pages in your 
tree, finding which branches contain meaningful info, which are full of meeting minutes 
and administrative pages, which are full of blanks, and which are golden nuggets in the 
caves of your spaces. 

run `ccandle cartographer --space SPACE` to get a quick analysis of the layout of the 
important information in your spaces.


## move pages in your Confluence hierarchy in bulk
Though a stronger link network *should* be our focus, many readers will still expect 
page hierarchies to be intuitive and usable. 

run `ccandle move-pages NEW-PARENT PAGE-IDS` to shift a list of pages to your selected 
new parent.


## gain deep insights into your corpus
Confluence doesn't surface so much useful meta-information. If you're a Confluence 
gardener, though, data is useful. That's where ccandle's `stats` function comes in. Try 
- `ccandle stats authors` to get a list of the most prolific editors in a space or 
across your corpus
- `ccandle stats links orphans` to see a share of orphaned pages across your tracked 
spaces
- `ccandle stats links incoming PAGE_ID` to see all incoming links for a page (you can 
do this on Confluence Cloud, by pretending to delete a page, then backing out...but this 
is probably a teensy-weensy bit easier)
- `ccandle stats links popular` to find the most 'popular' pages in your corpus / a 
specific space; e.g. find the most-linked to pages
- `ccandle stats links cross-space SPACE_ID` to find which spaces are most closely 
related to this one, to better understand how teams and topics relate to each other

Not enough insight? Run `ccandle sql query QUERY` to run arbitrary db queries on your 
stored pages.


## track progress across time with snapshots and benchmarking
Compare the current state of your corpus with an older snapshot by running `ccandle 
benchmark`. By default, a new snapshot is taken every 30 days, but you can set a 
different automatic frequency with `ccandle benchmark snapshots frequency DAYS`, or 
turn off auto-snapshots by setting frequency to -1.