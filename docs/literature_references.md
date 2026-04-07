# Literature References for Quantification Wound Healing Paper

Compiled: March 2026

---

## PART 1: COMPUTATIONAL METHODOLOGY

### 1. Existing Wound Healing Quantification Tools

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 1 | Gebaeck T, Schulz MMP, Koumoutsakos P, Detmar M. TScratch: a novel and simple software tool for automated analysis of monolayer wound healing assays. *BioTechniques* 46(4):265-274, 2009 | 10.2144/000113083 | TScratch -- curvelet-based tool; primary comparator |
| 2 | Suarez-Arnedo A et al. An ImageJ plugin for the high throughput image analysis of in vitro scratch wound healing assays. *PLOS ONE* 15(7):e0232565, 2020 | 10.1371/journal.pone.0232565 | ImageJ plugin for wound area/width |
| 3 | Vargas A et al. Robust quantitative scratch assay. *Bioinformatics* 32(9):1439-1440, 2016 | 10.1093/bioinformatics/btv746 | RQSA -- statistical outlier rejection, migration rate |
| 4 | Nunes Viana M et al. AIM: A Computational Tool for the Automatic Quantification of Scratch Wound Healing Assays. *Applied Sciences* 7(12):1237, 2017 | 10.3390/app7121237 | AIM tool -- benchmarked vs TScratch |
| 5 | Zordan MD et al. A high throughput, interactive imaging, bright-field wound healing assay. *Cytometry A* 79(3):227-232, 2011 | 10.1002/cyto.a.21029 | HT texture-based wound quantification in 96-well |
| 6 | Schindelin J et al. Fiji: an open-source platform for biological-image analysis. *Nature Methods* 9:676-682, 2012 | 10.1038/nmeth.2019 | Fiji platform underlying many plugins |
| 7 | McQuin C et al. CellProfiler 3.0: Next-generation image processing for biology. *PLOS Biology* 16(7):e2005970, 2018 | 10.1371/journal.pbio.2005970 | CellProfiler -- general bioimage analysis |
| 8 | Martinotti S et al. A novel method for evaluating and visualizing scratch wound healing assays using level-set and image sector analysis. *PNAS Nexus* 4(11):pgaf355, 2025 | 10.1093/pnasnexus/pgaf355 | Level-set + sector analysis (recent) |
| 9 | Zaritsky A et al. Live time-lapse dataset of in vitro wound healing experiments. *GigaScience* 4(1), 2015 | 10.1186/s13742-015-0049-6 | Benchmark time-lapse wound dataset |

### 2. Deep Learning Approaches (contrast with training-free design)

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 10 | Ronneberger O, Fischer P, Brox T. U-Net: Convolutional Networks for Biomedical Image Segmentation. *MICCAI 2015*, LNCS 9351:234-241 | 10.1007/978-3-319-24574-4_28 | U-Net -- foundational DL segmentation |
| 11 | Dogru D et al. An automated in vitro wound healing microscopy image analysis approach utilizing U-net-based deep learning methodology. *BMC Medical Imaging* 24:152, 2024 | 10.1186/s12880-024-01332-2 | U-Net variants applied to wound healing |
| 12 | Lehmann T et al. Virtually Objective Quantification of in vitro Wound Healing Scratch Assays with the Segment Anything Model. *arXiv* 2407.02187, 2024 | arXiv:2407.02187 | SAM foundation model on wound images |
| 13 | Naser MA et al. Automated Segmentation of Hepatic Tumor Cell Migration Using U-Net Models. *Springer*, 2025 | 10.1007/978-3-032-09044-7_30 | Attention U-Net/U-Net++ on wound images |
| 14 | Oldenburg J et al. Methodology for comprehensive cell-level analysis of wound healing experiments using deep learning in MATLAB. *BMC Mol Cell Biol* 22:1, 2021 | 10.1186/s12860-021-00369-3 | DL + cell-level analysis in wound healing |

### 3. Variance-Based Texture Analysis

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 15 | Koenig L et al. Segmentation of phase contrast microscopy images based on multi-scale local Basic Image Features histograms. *CMBBE: Imaging & Visualization* 5(5):358-368, 2017 | 10.1080/21681163.2015.1016243 | Multi-scale local texture for phase contrast |
| 16 | Yin Z, Kanade T, Chen M. Understanding the phase contrast optics to restore artifact-free microscopy images for segmentation. *Medical Image Analysis* 16(5):1047-1062, 2012 | 10.1016/j.media.2011.12.006 | Phase contrast artifacts -- motivates variance over intensity |
| 17 | Vicar T et al. Cell segmentation methods for label-free contrast microscopy: review and comprehensive comparison. *BMC Bioinformatics* 20:121, 2019 | 10.1186/s12859-019-2880-8 | Review of label-free segmentation methods |
| 18 | Ambrossio PE et al. Automated Cell Foreground-Background Segmentation with Phase-Contrast Microscopy Images: An Alternative to Machine Learning. *Bioengineering* 9(2):81, 2022 | 10.3390/bioengineering9020081 | Training-free phase contrast segmentation |
| 19 | Loizou CP et al. Adaptable texture-based segmentation by variance and intensity. *Skin Res Technology* 22(4):412-423, 2016 | 10.1111/srt.12281 | Variance+intensity texture segmentation in biomedical imaging |

### 4. Temporal Constraints in Biological Image Analysis

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 20 | Guan D et al. Domain Adaptive Video Segmentation via Temporal Consistency Regularization. *ICCV 2021* | 10.1109/ICCV48922.2021.00766 | Temporal consistency regularization for video segmentation |
| 21 | Bragantini J et al. Ultrack: pushing the limits of cell tracking across biological scales. *Nature Methods*, 2025 | 10.1038/s41592-025-02778-0 | Ultrack -- temporal consistency in cell tracking |
| 22 | Lee K et al. DeepSea is an efficient deep-learning model for single-cell segmentation and tracking in time-lapse microscopy. *Cell Reports Methods* 3(7):100523, 2023 | 10.1016/j.crmeth.2023.100523 | Temporal information for time-lapse segmentation |
| 23 | Li K et al. Image segmentation and dynamic lineage analysis in single-cell fluorescence microscopy. *Cytometry A* 73A(5):376-386, 2008 | 10.1002/cyto.a.20527 | Level-set + volume conservation in time-lapse |

### 5. RANSAC and Robust Fitting / Signal Processing

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 24 | Fischler MA, Bolles RC. Random sample consensus: a paradigm for model fitting. *Comm ACM* 24(6):381-395, 1981 | 10.1145/358669.358692 | Original RANSAC paper |
| 25 | Savitzky A, Golay MJE. Smoothing and differentiation of data by simplified least squares procedures. *Analytical Chemistry* 36(8):1627-1639, 1964 | 10.1021/ac60214a047 | Original Savitzky-Golay filter |
| 26 | van der Walt S et al. scikit-image: image processing in Python. *PeerJ* 2:e453, 2014 | 10.7717/peerj.453 | scikit-image Python library |

### 6. Wound Healing Assay Reviews

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 27 | Liang CC, Park AY, Guan JL. In vitro scratch assay: a convenient and inexpensive method for analysis of cell migration in vitro. *Nature Protocols* 2(2):329-333, 2007 | 10.1038/nprot.2007.30 | Canonical scratch assay protocol |
| 28 | Jonkman JE et al. An introduction to the wound healing assay using live-cell microscopy. *Cell Adhes Migr* 8(5):440-451, 2014 | 10.4161/cam.36224 | Technical review: live-cell microscopy wound assay |
| 29 | Grada A et al. Research techniques made simple: analysis of collective cell migration using the wound healing assay. *J Invest Dermatol* 137(2):e11-e16, 2017 | 10.1016/j.jid.2016.11.020 | Collective cell migration via wound assay |
| 30 | Stamm A et al. In vitro wound healing assays -- state of the art. *BioNanoMaterials* 17(1-2):79-87, 2016 | 10.1515/bnm-2016-0002 | State-of-the-art review of wound assay methods |
| 31 | Ashby WJ, Zijlstra A. Established and novel methods of interrogating two-dimensional cell migration. *Integrative Biology* 4(11):1338-1350, 2012 | 10.1039/c2ib20154b | Review of 2D cell migration assays |
| 32 | Pinto BI et al. Comparison of in vitro scratch wound assay experimental procedures. *Biochem Biophys Rep* 33:101423, 2023 | 10.1016/j.bbrep.2023.101423 | Comparison of scratch assay procedures |
| 33 | Yarrow JC et al. A high-throughput cell migration assay using scratch wound healing, a comparison of image-based readout methods. *BMC Biotechnology* 4:21, 2004 | 10.1186/1472-6750-4-21 | Early comparison of image-based readout methods |
| 34 | Poujade M et al. Advancing in vitro cell migration studies: a review of open-source analytical platforms. *Cell Adhes Migr*, 2025 | 10.1080/19336918.2025.2488116 | Most recent review of open-source platforms |
| 35 | Treloar KK, Simpson MJ. Sensitivity of edge detection methods for quantifying cell migration assays. *PLOS ONE* 8(6):e67389, 2013 | 10.1371/journal.pone.0067389 | Edge detection sensitivity for wound quantification |
| 36 | Topman G et al. The frequent sampling of wound scratch assay reveals the opportunity window for quantitative evaluation of cell motility-impeding drugs. *Front Cell Dev Biol* 9:640972, 2021 | 10.3389/fcell.2021.640972 | Frequent sampling reveals optimal drug-effect windows |

---

## PART 2: BIOLOGICAL CONTEXT

### A. Myoblast / Skeletal Muscle Cell Migration

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 37 | Goetsch KP, Myburgh KH, Niesler CU. Optimization of the scratch assay for in vitro skeletal muscle wound healing analysis. *Anal Biochem* 411(1):158-160, 2011 | 10.1016/j.ab.2010.12.012 | Scratch assay optimized for myoblasts |
| 38 | Goetsch KP et al. In vitro myoblast motility models: investigating migration dynamics for the study of skeletal muscle repair. *J Muscle Res Cell Motil* 34(5-6):333-342, 2013 | 10.1007/s10974-013-9364-7 | Review of myoblast motility models |
| 39 | Kowalski K et al. Stem cells migration during skeletal muscle regeneration -- the role of Sdf-1/Cxcr4 and Sdf-1/Cxcr7 axis. *Cell Adhes Migr* 11(4):384-398, 2017 | 10.1080/19336918.2016.1227911 | SDF-1/CXCR4 chemotaxis in muscle regeneration |
| 40 | Ele A et al. Cellular dynamics of myogenic cell migration: molecular mechanisms and implications for skeletal muscle cell therapies. *EMBO Mol Med* 12(12):e12357, 2020 | 10.15252/emmm.202012357 | Molecular regulators of myogenic cell migration |
| 41 | Webster MT, Fan CM. c-MET regulates myoblast motility and myocyte fusion during adult skeletal muscle regeneration. *Development* 140(22):4586-4596, 2013 | 10.1242/dev.098210 | c-MET regulates myoblast motility |

### B. Renin-Angiotensin System in Muscle Repair

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 42 | Cohn RD et al. Angiotensin II type 1 receptor blockade attenuates TGF-beta-induced failure of muscle regeneration in multiple myopathic states. *Nature Medicine* 13(2):204-210, 2007 | 10.1038/nm1536 | Landmark: AT1R blockade rescues dystrophic muscle via TGF-beta |
| 43 | Bedair HS et al. Angiotensin II receptor blockade administered after injury improves muscle regeneration and decreases fibrosis in normal skeletal muscle. *Am J Sports Med* 36(8):1548-1554, 2008 | 10.1177/0363546508315470 | AT1R blockade improves non-dystrophic muscle regeneration |
| 44 | Yoshida T et al. Angiotensin II inhibits satellite cell proliferation and prevents skeletal muscle regeneration. *J Biol Chem* 288(33):23823-23832, 2013 | 10.1074/jbc.M112.449074 | AngII inhibits satellite cell proliferation via AT1R-Notch |
| 45 | Yoshida T et al. Regulation of muscle satellite cell activation and chemotaxis by angiotensin II. *PLOS ONE* 5(12):e15212, 2010 | 10.1371/journal.pone.0015212 | AngII regulates satellite cell activation and chemotaxis |
| 46 | Lemos DR et al. Angiotensin-II drives human satellite cells toward hypertrophy and myofibroblast trans-differentiation. *Int J Mol Sci* 20(19):4912, 2019 | 10.3390/ijms20194912 | AngII drives satellite cell-to-myofibroblast switch |
| 47 | Cabello-Verrugio C et al. Renin-angiotensin system: an old player with novel functions in skeletal muscle. *Med Res Rev* 35(3):437-463, 2015 | 10.1002/med.21343 | Comprehensive RAS in skeletal muscle review |
| 48 | Morales MG et al. Angiotensin-(1-7) improves skeletal muscle regeneration. *Exp Physiol*, 2024 | 10.1113/EP091547 | Ang-(1-7) improves muscle regeneration |
| 49 | Morales MG et al. Inhibition of ACE decreases skeletal muscle fibrosis in dystrophic mice. *Cell Tissue Res* 353(2):215-228, 2013 | 10.1007/s00441-013-1642-6 | ACE inhibition reduces dystrophic fibrosis via CTGF |
| 50 | Kurosaka M et al. Reduced angiogenesis and delay in wound healing in AT1a receptor-deficient mice. *Biomed Pharmacother* 63(9):627-634, 2009 | 10.1016/j.biopha.2009.01.001 | Caution: AT1R deficiency delays skin wound healing |

### C. TGF-beta / ALK5 Pathway in Cell Migration and Muscle

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 51 | Inman GJ et al. SB-431542 is a potent and specific inhibitor of ALK4, ALK5, and ALK7. *Mol Pharmacol* 62(1):65-74, 2002 | 10.1124/mol.62.1.65 | SB-431542 ALK5 inhibitor characterization |
| 52 | Delaney K et al. The role of TGF-beta1 during skeletal muscle regeneration. *Cell Biol Int* 41(7):706-715, 2017 | 10.1002/cbin.10725 | TGF-beta1 in skeletal muscle regeneration review |
| 53 | Li Y et al. Transforming growth factor-beta1 induces the differentiation of myogenic cells into fibrotic cells. *Am J Pathol* 164(3):1007-1019, 2004 | 10.1016/s0002-9440(10)63188-4 | TGF-beta1 drives myogenic-to-fibrotic switch |
| 54 | Girardi F et al. TGFbeta signaling curbs cell fusion and muscle regeneration. *Nature Comms* 12:750, 2021 | 10.1038/s41467-020-20289-8 | TGF-beta curbs cell fusion |
| 55 | Ceco E, McNally EM. Modifying muscular dystrophy through TGF-beta. *FEBS J* 280(17):4198-4209, 2013 | 10.1111/febs.12266 | TGF-beta in muscular dystrophy |
| 56 | Weiss T et al. Effect of TGF-beta receptor I inhibitors on myotube formation in vitro. *Sci Rep* 15:87934, 2025 | 10.1038/s41598-025-09381-5 | 5 TGFbetaRI inhibitors on C2C12 myotubes (recent) |
| 57 | Weiss T et al. Effects of TGF-beta receptor I inhibitors on myofibroblast differentiation and myotube formation. *Front Cell Dev Biol* 13:1636884, 2025 | 10.3389/fcell.2025.1636884 | TGFbetaRI inhibitors myofibroblast/myotube |
| 58 | Loiselle AE et al. TGF-beta1 induces transdifferentiation of myoblasts into myofibroblasts via SK1/S1P3 axis. *Mol Biol Cell* 20(15):3505-3513, 2009 | 10.1091/mbc.e09-09-0812 | TGF-beta1 myoblast-to-myofibroblast mechanism |
| 59 | Ismaeel A et al. Role of TGF-beta/SMAD/YAP/TAZ signaling in skeletal muscle fibrosis. *Am J Physiol Cell*, 2024 | 10.1152/ajpcell.00541.2024 | TGF-beta/Smad/YAP/TAZ in muscle fibrosis |
| 60 | Lach-Trifilieff E et al. Inhibition of ALK4/5 attenuates cancer cachexia-associated muscle wasting. *Sci Rep* 9:9826, 2019 | 10.1038/s41598-019-46178-9 | ALK4/5 inhibition prevents cachexia wasting |

### D. Collective Cell Migration Theory

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 61 | Haeger A et al. Collective cell migration: implications for wound healing and cancer invasion. *Burns & Trauma* 1(1):21-28, 2013 | 10.4103/2321-3868.113331 | Collective migration: wound healing vs cancer |
| 62 | Reffay M et al. Mechanical interactions among followers determine the emergence of leaders. *Nature Comms* 9:3693, 2018 | 10.1038/s41467-018-05927-6 | Follower mechanics determine leader emergence |
| 63 | Vishwakarma M et al. Leader cell positioning drives wound-directed collective migration in TGFbeta-stimulated epithelial sheets. *Mol Biol Cell* 25(9):1586-1593, 2014 | 10.1091/mbc.e14-01-0697 | TGF-beta drives leader cell positioning |
| 64 | Ng JY, Du J. Who's really in charge: diverse follower cell behaviors in collective cell migration. *Trends Cell Biol* 33(10):888-902, 2023 | 10.1016/j.tcb.2023.04.002 | Follower cells steer collective migration |

### E. Mathematical Models of Wound Closure

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 65 | Jin W et al. Estimating cell diffusivity and proliferation rate by interpreting IncuCyte ZOOM assay data using Fisher-Kolmogorov model. *BMC Systems Biology* 9:38, 2015 | 10.1186/s12918-015-0182-y | Separates migration from proliferation |
| 66 | Arciero JC et al. Continuum model of collective cell migration in wound healing and colony expansion. *Biophys J* 100(3):535-543, 2011 | 10.1016/j.bpj.2010.11.083 | Continuum model of collective migration |
| 67 | Maini PK et al. Scratch assay microscopy: a reaction-diffusion equation approach. *Math Biosci* 330:108482, 2020 | 10.1016/j.mbs.2020.108482 | Reaction-diffusion for scratch assay data |
| 68 | Simpson MJ et al. Quantifying the roles of cell motility and cell proliferation in a circular barrier assay. *J R Soc Interface* 10(82):20130007, 2013 | 10.1098/rsif.2013.0007 | Motility vs proliferation contributions |

### F. AngII-TGF-beta Crosstalk

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 69 | Murphy AM et al. Modulation of angiotensin II signaling in the prevention of fibrosis. *Fibrogenesis Tissue Repair* 8:7, 2015 | 10.1186/s13069-015-0023-z | AngII + TGF-beta share Smad signaling |
| 70 | Rodriguez-Vita J et al. Essential role of Smad3 in angiotensin II-induced vascular fibrosis. *Circ Res* 96(12):1292-1299, 2005 | 10.1161/01.RES.0000171524.42914.37 | AngII activates Smad3 (shared with ALK5) |
| 71 | Wang W et al. Angiotensin II activates the Smad pathway during epithelial mesenchymal transdifferentiation. *Kidney Int* 74(5):585-595, 2008 | 10.1038/ki.2008.302 | AngII activates Smad2/3 TGF-beta-independently |

### G. Dose-Response and High-Throughput Screening

| # | Reference | DOI | Relevance |
|---|-----------|-----|-----------|
| 72 | Schmidt K et al. Automated high-throughput live cell monitoring of scratch wound closure. *SLAS Technology*, 2024 | 10.1177/11795972241295619 | Automated HT wound closure monitoring |
| 73 | Justus CR et al. In vitro cell migration quantification method for scratch assays. *J Vis Exp*, 2014 | PMID: 24747722 | Foundational scratch assay quantification protocol |
