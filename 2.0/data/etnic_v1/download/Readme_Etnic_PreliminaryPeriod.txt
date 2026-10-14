
Please note that we are releasing this preliminary version of the embeddings-based version of TNIC early due to popular request, but also note that we are doing some additional testing of this data and might further fine-tune how we purge any residual boilerplate content from the embeddings representation.  Yet we are reasonably confident that any final changes should be small or perhaps no further changes will be made.  We hope to finalize this data in the next few months.  

ETNIC data has three advantages.  

1.  It uses embedding technology and is roughly 20-25% stronger in terms of the signal predicting accounting characteristics like profitability than is baseline TNIC.  For example, if you predict operating profitability / assets for a focal firm with the average of the focal firm's competitors, the R-squared of the regression is 20-25% higher than competitors identified using the previous cosine-similarity based TNIC, which in turn was on an even more substantial order of magnitude higher than previous SIC or NAICS based competitor identification as shown in our 2016 JPE article cited below. 

2. The extended ETNIC covers all firms in Compustat with an available 10-K, whereas baseline TNIC also required that a firm have a valid CRSP observation.  

3.  IMPORTANT:  We use separately trained doc2vec models in each period to create yearly ETNIC scores.  These yearly trained doc2vec models ensures that this data is not exposed to any look-ahead bias (See Note 3 below, which also explains why we use doc2vec in this release rather than models such as BERT or GPT).

If you use this data for a research project, please save the data you download and note the time-stamp on the database you downloaded.  This will identify the version you can reference in your data and methods section.  You should include this preliminary data in your replication package when you publish your work, as we will not maintain older copies of this data if it is changed.  Again, we don't see any material changes as likely but to ensure replicability, please note the time stamp.

The ETNIC (Embeddings-based TNIC) data is the result of three research papers that you might consider citing.

Paper 1. Scope, Scale and Competition: The 21st Century Firm
Gerard Hoberg and Gordon Phillips, 2025, forthcoming Journal of Finance.

Links: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3746660 & https://onlinelibrary.wiley.com/doi/10.1111/jofi.13400


Relevant notes about this paper and ETNIC
	*Note 1: this paper develops the 300 dimensional doc2vec embedding of the TNIC database.  A separate doc2vec model is trained in each year using all item 1 business descriptions from that year and all yearly doc2vec vectors for each firm are obtained using the model trained in the same year.  Then 300 element vectors representing each company in each year are thus extracted from the annual doc2vec models.  Firm pairwise similarity is then computed by taking the cosine similarity of any pair of firms in a given year purged of boilerplate (see note about boilerplate purging below).

	*Note 2: The ETNIC database has more coverage than the baseline TNIC database.  This is because baseline TNIC data has always strictly required that all firms in the database are publicly traded.  In order to be in the baseline TNIC database, a firm must exist in the WRDS merged CRSP-Compustat database and must have a valid link to CRSP.  The new ETNIC database relaxes that filter and more broadly includes any firm in the CRSP-Compustat merged database for which we can identify a machine-readable 10-K.  That is, the ETNIC database does NOT additionally require that the firm have a valid CRSP link in the given year.  We decided to extend the database in this way as users can decide on their own if they wish to just use the firms with a valid CRSP link.  Thus ETNIC offers more flexibility as an additional enhancement.

	*Note 3: As noted in the advantages above, the work in the above JF 2025 paper notes that ETNIC has roughly 20-25% more explanatory power regarding firm characteristics than does the baseline TNIC database.  Hence, as expected, embeddings technologies facilitate a stronger signal extraction.  We also note that ETNIC is based on separately trained yearly doc2vec models and does not have any look ahead bias. This is why we do not currently use measures based on ex-post trained models such as ChatGPT or BERT.  Because industry classifications are so widely used, and out of an abundance of caution, we believe that fully non-biased embeddings-based TNIC are the next step for release until more research is done regarding the appropriate use of more sophisticated large language models/generative AI that would ensure they are not prone to look ahead issues.


Paper 2. Text-Based Network Industries and Endogenous Product Differentiation
Gerard Hoberg and Gordon Phillips, Journal of Political Economy(October 2016), 124 (5) 1423-1465.

Link: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1520062

Note: This paper documents the work behind traditional TNIC industry classifications using raw text (above document how to use doc2vec).  So this is a historical reference only.


Paper 3. Using Representation Learning and Web Text to Identify Competitors
Gerard Hoberg, Craig Knoblock, Gordon Phillips, Jay Pujara, Zhiqiang Qiu and Louiqa Raschid

Link: https://facultynew.tuck.dartmouth.edu/uploads/gordonPhillips/publications/BOKN_Journal___INFORMS_MnSc.pdf

Relevant notes about this paper
*Note: This paper is primarily dedicated to the website-based TNIC database (WTNIC) creation that will include private firms (coming soon). But relevant to ETNIC and this data, the paper also develops algorithms for purging boilerplate content from embeddings.  Although the best purging method for 10-Ks is different from that for websites, work relating to boilerplate purging was developed by this team.  Below we note the purging procedure that works best for 10-Ks and thus how the ETNIC data here was purged of boilerplate.

**********************************************************************************************************************

************************************* Boilerplate Purging doc2vec Vectors ********************************************

A cosine similarity without modification for doc2vec vectors requires simply taking the dot product of normalized vectors for two firms.  Our premise on boilerplate purging is that some of the 300 dimensions we have in our doc2vec space represent less informative themes and are thus likely boilerplate.  Our goal is to downweight such ininformative dimensions.  

Our boilerplate purged cosine similarity is simply the normalized weighted dot product where each dimension is weighted by the relative size of its regression coefficient in predicting baseline TNIC similarity scores at the 10\% granularity level (consistent with granularity of SIC-1, which is the minimum informed granularity).  If a doc2vec dimension has no ability to predict the baseline TNIC score, it therefore gets very little weight as it is likely boilerplate.  If it has a strong ability, the dimension will get high weight.  We find that this procedure improves the quality of the peers meaningfully as 10-Ks do have some boilerplate content.  Note that our baseline TNIC scores are already purged of boilerplate content as their similarities are based on nouns and proper nouns.


**********************************************************************************************************************
********************************************** Important Detail ******************************************************

Please note that this readme is a general source of information about the ETNIC database.  Please still review the readme files associated with any resources you download, as their content is specific to each data file and is not redundant to what is here.

All files available on this web page are derived from the beta version of ETNIC.  Please go to the regular TNIC database homepage if you came to this page in error:

https://hobergphillips.tuck.dartmouth.edu/



