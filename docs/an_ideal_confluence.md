# An ideal Confluence
An ideal Confluence is:
- self navigable
- comprehensive
- not stale
- with good quality pages

This is of course, easier said than done. Even measuring these dimensions is not trivial 
when project scope, number of pages, spaces, and even domain varies between teams. 

Instead of outlining content goals, we'll outline here *structural* goals for an ideal 
Confluence.  

## Breaking out of single parent hierarchy makes navigation more intuitive
<img src="docs/images/page_network_topology.png" width="700" alt="Two approaches to Confluence page graphs">

Typical Confluence instances rely on a single parent hierarchy of pages, but knowledge 
doesn't work like that. Yes, we can force anything into such a graph using the Dewey-Decimal 
system, but any bit of knowledge more naturally is structured as belonging to a set of 
overlapping categories. For example, the RS-25 rocket shuttle engines on Wikipedia are under 
the categories of 'space shuttle program,' 'rocket engines,' 'space launch system', 'rocket 
engines using the staged combustion cycle,' and still others.  

<img src="docs/images/overlapping_categories.png" width="500" alt="Overlapping categories more closely matches our brain's way of classifying knowledge">

Wikipedia uses *categories*, but in Confluence the closest analogue I've found is the use 
of *labels*. With ccandle, you can use a finely-tuned search via sql query, then bulk edit 
labels. 

## Wikipedia-style navboxes guide readers along a topic
<img src="docs/images/wikipedia_navboxes_and_categories.png" width="500" alt="Wikipedia leverages sets of curated links to guide readers through a topic">

Wikipedia has over 7 million articles on its English encyclopedia. Nowhere will you find a 
Confluence-style page tree. One structural feature Wikipedia leverages to improve self-
navigability is *navboxes*. These are a kind of template page element with a set of curated 
links on a topic. Why should a user search like a lotto machine for a topic, when you can 
hold their hand and guide them through its most important pages, with a navbox?

Our approach to recreate this in Confluence is with the use of an *excerpt*
(reusable across pages) having a *filter by label* widget inside. This excerpt can then be 
'included' into other pages via an *excerpt-include* widget. 

<img src="docs/images/navboxes_in_confluence.png" width="500" alt="an example showing how to create a navbox in Confluence.">

To help you get started leveraging navboxes in your documentation, ccandle provides a 
bulk workflow for clearing and inserting navbox excerpts from a given page, along with 
tracking which pages in your corpus are navbox *sources* vs *consumers*.

## Better leading paragraphs make 'near misses' recoverable
Gotta document the document machine...please wait...

## Landing pages streamline navigation
Gotta document the document machine...please wait...

## Canonical introductory pages put an entire overview in one place 
Gotta document the document machine...please wait...
