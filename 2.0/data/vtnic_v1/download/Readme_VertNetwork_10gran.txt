****************************
TOP LEVEL NOTE: This is the 10% granularity version of the VTNIC (Vertical TNIC) database, which contains the firm-pairs that have vertical relatedness scores 
in the top 10% of all pairwise scores in the given year.  Please see the primary reference below for a description of network granularity and for all details.
The 10% granularity file is smaller than the full network and is likely what most research projects should use (relatedness outside the top 10% is generally modest).

****** NOTE:  Please read the technical descriptions below before using the data.  

This file accompanies the VTNIC (Vertical TNIC) 10% granularity relatedness database and describes where the data comes from, and the relevant
papers that should be cited when providing academic references, and some important technical details regarding its usage.
Please read the primary reference below and the technical details below in full before using this data.  These details are 
critically important to ensure proper usage.

This data includes for each firm the ***directed*** vertical relatedness scores for all other firms in our sample in the given year (see Technical Note #2 below). 
The first two columns of data identify the pair of firms (gvkeys) that the given vertical score observation in the third column corresponds to.
Because the scores are directed, the interpretation of a given row containing (gvkey1 gvkey2 vertscore) is that firm gvkey1's vertical upstream potential relative
to firm gvkey2 is equal to vertscore.  If there is another observation in the database for which gvkey1 and gvkey2 are reversed, this observation would
be interpreted as having the other direction and is firm gvkey1's vertical downstream potential relative to firm gvkey2.  In some cases, the reversed 
observation will not be present, however, and this would mean that the given pair are not related enough to be part of the 10% granularity.  If you want to see
relatedness scores for all pairs, even those below 10%, you will need to download the larger complete granularity version of the VTNIC network.

For a complete description of this data, please read the data and methodology section of the primary paper reference below.


**************************************************************************************************************
**************************************************************************************************************
********************************************** Citations *****************************************************
********************************************** Citations *****************************************************
********************************************** Citations *****************************************************
**************************************************************************************************************
**************************************************************************************************************

This data is the result of a large research project initiated in early 2012 by Laurent Fresard, Gerard Hoberg and Gordon Phillips.
The intent of the project is to better understand the role of vertical relatedness across product markets  
and to examine the link between vertical relatedness and innovation.  The data is the result of innovations described in the following
paper.  As such, this article should be cited when using this data for the purpose of academic research.

Primary reference:
Innovation Activities and Integration through Vertical Acquisitions
Laurent Fresard, Gerard Hoberg, and Gordon Phillips, Review of Financial Studies (accepted 2019).

***********
Auxiliary reference 1: This articles is a precursor to VTNIC.  In particular, it develops the original horizontal TNIC industries.

Text-Based Network Industries and Endogenous Product Differentiation
Gerard Hoberg and Gordon Phillips, Journal of Political Economy (October 2016), 124 (5) 1423-1465.

***********
Auxiliary reference 2: This articles is also a precursor to VTNIC.  It uses horizontal relatedness data (TNIC) to study mergers and acquisitions.
  This article is relevant especially because the primary VTNIC paper above also studies M&A.  The two papers are complementary as the theories
  and results for vertically related product markets are distinct from those in horizontally related markets.  See the papers for details.

Product Market Synergies and Competition in Mergers and Acquisitions: A Text-Based Analysis
Gerard Hoberg and Gordon Phillips, Review of Financial Studies (October 2010) 23 (10), 3773-3811.


**********************************************************************************************************************
**********************************************************************************************************************
********************************************** Technical Details *****************************************************
********************************************** Technical Details *****************************************************
********************************************** Technical Details *****************************************************
**********************************************************************************************************************
**********************************************************************************************************************

Please read the following carefully to ensure proper usage of this data.

Technical Note 1) The data here is the full square relatedness matrix for firm pairs in our database in each year.  There is one file for all observations with the year column indicating
the year of the given pairwise score calculation.  Within a year, every pair of gvkey1 and gvkey2 can appear zero times, once, or twice.  If the pair are not highly related (at the 10% granularity or higher) in either vertical direction, the pair will not appear at all.  If one direction meets the 10% granularity cut off but not the other, then the pair will appear once.  If both directions indicate strong vertical relatedness, then the pair will appear twice.  If you want full information for all pairs, you will need to download the full granularity database instead of the 10% granularity database.

Technical Note 2) The vertical VTNIC data differs from the horizontal TNIC data in that the relatedness network is not symmetric like it is for TNIC data.  This is because 
vertical links relate to a supply chain and are thus directional.  That is, a given firm #1 could be more upstream relateive to firm #2 or vice a versa.  As explained in the 
primary reference paper above (please read the paper in detail to fully understand this relationship), we compute the relatedness scores using a triple product of matrices.  The
result is that a row of the relatedness matrix pertains to the firm for which upstream potential is to be computed and the column pertains to the firm for which downstream potential is
to be computed.  In the context of the data provided here, the column of data for gvkey1 indicates the firm for which the score in column 3 relates to its upstream potential relative to 
the firm gvkey2 for which the score relates to the downstream potential.  Indeed you will see that a specific gvkey-pair will appear as many as two times (as noted above) in the database (gvkey1 gvkey2 vertscore12) and (gvkey2 gvkey1 vertscore21) and vertscore12 will not equal vertscore12...  A final note on this topic is that some users of the data will be interested in vertical relatedness but might not care about direction.  

Technical Note 3) For convenience, these classifications DO include a record for the firm itself.  Thus, for all firms in the sample in a given year, one observation will appear in which gvkey1 and gvkey2 are the same.  For some calculations (for example to construct an industry control that excludes the firm itself), these records (those with gvkey1=gvkey2) should be dropped.  However, for other applications, it is important to keep the firm itself in the classification.  Hence we include these records to provide the most flexiblity possible.

Technical Note 4) Each file contains a gvkey1 and a gvkey2 variable in addition to the score variable.  It is important to note that we already did 
the merge to COMPUSTAT, so you do not have to repeat this.  The data contained here is not lagged.  Consider a COMPUSTAT firm with a fiscal year ending 
on Sept 30th, 1997, for example (i.e., the CSTAT variable datadate is 19970930).  The corresponding observations for this firm in the VTNIC database would have the
year set to 1997. These observations would be based on the product description of the 10-K report that was associated with this 9/30/1997 fiscal year end.  More generally, 
the year field in the TNIC database is always set to be the first four digits of the datadate variable (the year part) so the database uses the calendar year convention for
convenience.  Because this data is merged by fiscal year end, the pairwise links in this file should conveniently be viewed as being time-synchronous based on the year
identified as the first four digits of the datadate Compustat variable.



