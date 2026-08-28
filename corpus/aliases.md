# Search Aliases — corpus-wide synonym & abbreviation table

Purpose: BM25 search in `search.py` matches exact tokens only. Before searching,
expand the question's terms using this table and search BOTH forms (or the form
the textbook is likely to use). All six library books are US-English editions —
translate UK spellings in question stems to US spellings before searching.

Maintenance: append-only. When a solve escalates because the book said it under
different words, add the pair here.

## Abbreviations ↔ expansions

| Abbrev | Expansion (search this in the books) |
|---|---|
| SBO / LBO | small bowel obstruction / large bowel obstruction |
| GERD | gastroesophageal reflux disease |
| PUD | peptic ulcer disease |
| EGD | esophagogastroduodenoscopy, upper endoscopy |
| ERCP | endoscopic retrograde cholangiopancreatography |
| MRCP | magnetic resonance cholangiopancreatography |
| PTC | percutaneous transhepatic cholangiography |
| EUS | endoscopic ultrasound |
| FNA | fine-needle aspiration |
| HIDA | hepatobiliary iminodiacetic acid scan, cholescintigraphy |
| CBD / CBDE | common bile duct / common bile duct exploration |
| IOC | intraoperative cholangiography |
| LC | laparoscopic cholecystectomy |
| GIST | gastrointestinal stromal tumor |
| NET | neuroendocrine tumor (also "carcinoid") |
| PNET | pancreatic neuroendocrine tumor |
| HCC | hepatocellular carcinoma |
| CRC | colorectal cancer |
| FAP | familial adenomatous polyposis |
| HNPCC | hereditary nonpolyposis colorectal cancer = Lynch syndrome |
| IBD / UC / CD | inflammatory bowel disease / ulcerative colitis / Crohn disease |
| IPAA | ileal pouch-anal anastomosis |
| APR | abdominoperineal resection |
| LAR | low anterior resection |
| TME | total mesorectal excision |
| CME | complete mesocolic excision |
| TEM / TAMIS | transanal endoscopic microsurgery / transanal minimally invasive surgery |
| EMR / ESD | endoscopic mucosal resection / endoscopic submucosal dissection |
| LIFT | ligation of intersphincteric fistula tract |
| CRS / HIPEC | cytoreductive surgery / hyperthermic intraperitoneal chemotherapy |
| PMP | pseudomyxoma peritonei |
| LARS | low anterior resection syndrome |
| TPN / PN / EN | (total) parenteral nutrition / enteral nutrition |
| NGT | nasogastric tube |
| SSI | surgical site infection |
| VAP | ventilator-associated pneumonia |
| CLABSI | central line-associated bloodstream infection |
| ARDS | acute respiratory distress syndrome |
| SIRS / MODS | systemic inflammatory response syndrome / multiple organ dysfunction syndrome |
| AKI | acute kidney injury |
| CRRT / RRT | (continuous) renal replacement therapy |
| ECMO | extracorporeal membrane oxygenation |
| DVT / PE / VTE | deep venous thrombosis / pulmonary embolism / venous thromboembolism |
| IVC | inferior vena cava (filter) |
| HIT | heparin-induced thrombocytopenia |
| ITP | immune thrombocytopenic purpura |
| DIC | disseminated intravascular coagulation |
| FFP / PRBC / PCC | fresh frozen plasma / packed red blood cells / prothrombin complex concentrate |
| MTP | massive transfusion protocol |
| TXA | tranexamic acid |
| TEG / ROTEM | thromboelastography / rotational thromboelastometry |
| OPSI | overwhelming postsplenectomy infection |
| AAA | abdominal aortic aneurysm |
| TAAA | thoracoabdominal aortic aneurysm |
| EVAR / TEVAR | endovascular aneurysm repair / thoracic endovascular aortic repair |
| CEA | carotid endarterectomy — COLLISION: also carcinoembryonic antigen; pick by context |
| CAS / TCAR | carotid artery stenting / transcarotid artery revascularization |
| PAD | peripheral arterial disease |
| ABI | ankle-brachial index |
| CLI / CLTI | critical limb ischemia / chronic limb-threatening ischemia |
| AVF / AVG | arteriovenous fistula / arteriovenous graft |
| TOS | thoracic outlet syndrome |
| REBOA | resuscitative endovascular balloon occlusion of the aorta |
| FAST | focused assessment with sonography for trauma |
| ATLS | advanced trauma life support |
| GCS | Glasgow Coma Scale |
| ICP / TBI | intracranial pressure / traumatic brain injury |
| EDH / SDH / SAH | epidural / subdural / subarachnoid hemorrhage (hematoma) |
| BCVI | blunt cerebrovascular injury |
| ACS | abdominal compartment syndrome — COLLISION: also acute coronary syndrome; pick by context |
| DCS | damage control surgery |
| MEN | multiple endocrine neoplasia |
| PHPT / PTH / ioPTH | primary hyperparathyroidism / parathyroid hormone / intraoperative PTH |
| TSH | thyroid-stimulating hormone |
| RLN / SLN | recurrent laryngeal nerve / superior laryngeal nerve — COLLISION: SLN(B) also sentinel lymph node (biopsy) |
| MTC | medullary thyroid carcinoma |
| PTC (thyroid context) | papillary thyroid carcinoma — COLLISION with percutaneous transhepatic cholangiography |
| MNG | multinodular goiter |
| FNH | focal nodular hyperplasia |
| PSC / PBC | primary sclerosing cholangitis / primary biliary cholangitis (cirrhosis) |
| NAFLD / NASH | nonalcoholic fatty liver disease / steatohepatitis |
| MELD | Model for End-Stage Liver Disease |
| TIPS | transjugular intrahepatic portosystemic shunt |
| SBP | spontaneous bacterial peritonitis |
| HRS | hepatorenal syndrome |
| PVE / FLR | portal vein embolization / future liver remnant |
| ALPPS | associating liver partition and portal vein ligation for staged hepatectomy |
| IPMN / MCN | intraductal papillary mucinous neoplasm / mucinous cystic neoplasm |
| LAMN | low-grade appendiceal mucinous neoplasm |
| ZES | Zollinger-Ellison syndrome, gastrinoma |
| DCIS / LCIS | ductal / lobular carcinoma in situ |
| SLNB / ALND | sentinel lymph node biopsy / axillary lymph node dissection |
| NAC | neoadjuvant chemotherapy — COLLISION: also nipple-areola complex |
| TNBC | triple-negative breast cancer |
| NSM | nipple-sparing mastectomy |
| TRAM / DIEP | transverse rectus abdominis myocutaneous / deep inferior epigastric perforator flap |
| CDH | congenital diaphragmatic hernia |
| EA / TEF | esophageal atresia / tracheoesophageal fistula |
| NEC | necrotizing enterocolitis |
| HPS | hypertrophic pyloric stenosis |
| UPJ / VUR / PUV | ureteropelvic junction / vesicoureteral reflux / posterior urethral valves |
| RCC | renal cell carcinoma |
| BPH / TURP | benign prostatic hyperplasia / transurethral resection of the prostate |
| RYGB | Roux-en-Y gastric bypass |
| SG / LSG | (laparoscopic) sleeve gastrectomy |
| BPD-DS | biliopancreatic diversion with duodenal switch |
| AGB | adjustable gastric band |
| POEM | peroral endoscopic myotomy |
| LES / UES | lower / upper esophageal sphincter |
| PEH | paraesophageal hernia |
| PEG | percutaneous endoscopic gastrostomy |
| CABG / PCI | coronary artery bypass grafting / percutaneous coronary intervention |
| TAVR | transcatheter aortic valve replacement |
| ASD / VSD / PDA / TOF | atrial septal defect / ventricular septal defect / patent ductus arteriosus / tetralogy of Fallot |
| LVAD | left ventricular assist device |
| ERAS | enhanced recovery after surgery |
| PONV | postoperative nausea and vomiting |
| MH | malignant hyperthermia |
| ASA | American Society of Anesthesiologists class — COLLISION: also aspirin |
| NSQIP | National Surgical Quality Improvement Program |
| SMA / IMA / SMV | superior mesenteric artery / inferior mesenteric artery / superior mesenteric vein |
| MALS | median arcuate ligament syndrome, celiac artery compression |
| NOM | nonoperative management |
| WLE | wide local excision |

## Eponyms ↔ descriptive terms (search both directions)

| Eponym | Descriptive equivalent |
|---|---|
| Hartmann procedure | sigmoid resection with end colostomy, rectal stump closure |
| Whipple procedure | pancreaticoduodenectomy — SPELLING: books use both "pancreaticoduodenectomy" and "pancreatoduodenectomy" |
| Whipple triad | insulinoma diagnostic triad |
| Graves disease | diffuse toxic goiter |
| Plummer disease | toxic multinodular goiter / toxic adenoma |
| Hashimoto thyroiditis | chronic lymphocytic thyroiditis |
| de Quervain thyroiditis | subacute granulomatous thyroiditis |
| Riedel thyroiditis | invasive fibrous thyroiditis |
| Conn syndrome | primary hyperaldosteronism |
| Addison disease | primary adrenal insufficiency |
| Sipple / Wermer syndrome | MEN2A / MEN1 |
| Zollinger-Ellison | gastrinoma |
| Verner-Morrison | VIPoma, WDHA syndrome |
| Sister Mary Joseph nodule | umbilical metastasis |
| Virchow node | left supraclavicular lymphadenopathy |
| Krukenberg tumor | gastric cancer ovarian metastasis |
| Blumer shelf | rectal shelf, pelvic (pouch of Douglas) metastasis |
| Trousseau syndrome | migratory thrombophlebitis (malignancy) |
| Courvoisier sign | palpable nontender gallbladder with jaundice |
| Charcot triad / Reynolds pentad | cholangitis: fever, jaundice, RUQ pain (+ shock, confusion) |
| Mirizzi syndrome | cystic duct stone compressing common hepatic duct |
| Bouveret syndrome | gallstone ileus with duodenal/gastric outlet obstruction |
| Klatskin tumor | hilar / perihilar cholangiocarcinoma |
| Caroli disease | congenital intrahepatic bile duct dilation (Todani type V) |
| Budd-Chiari syndrome | hepatic venous outflow obstruction |
| Kasai procedure | (hepatic) portoenterostomy for biliary atresia |
| Puestow procedure | lateral (longitudinal) pancreaticojejunostomy |
| Frey / Beger procedure | duodenum-preserving pancreatic head resection variants |
| Ogilvie syndrome | acute colonic pseudo-obstruction |
| Hirschsprung disease | congenital aganglionic megacolon |
| Ladd procedure / bands | malrotation operation / peritoneal bands |
| Ramstedt operation | pyloromyotomy |
| Nissen fundoplication | complete 360-degree fundoplication |
| Toupet / Dor fundoplication | partial posterior 270 / partial anterior fundoplication |
| Heller myotomy | esophagocardiomyotomy for achalasia |
| Hill repair | posterior gastropexy |
| Collis gastroplasty | esophageal lengthening procedure |
| Ivor Lewis / McKeown | transthoracic esophagectomy (two-stage / three-field) |
| Zenker diverticulum | pharyngoesophageal (cricopharyngeal) pulsion diverticulum, Killian triangle |
| Boerhaave syndrome | spontaneous (postemetic) esophageal perforation |
| Schatzki ring | distal esophageal mucosal ring |
| Barrett esophagus | intestinal metaplasia of distal esophagus |
| Mallory-Weiss tear | gastroesophageal junction mucosal laceration |
| Dieulafoy lesion | submucosal caliber-persistent artery bleed |
| Curling / Cushing ulcer | stress ulcer of burns / of head injury |
| Menetrier disease | hypertrophic gastropathy |
| Billroth I / II | gastroduodenostomy / gastrojejunostomy reconstruction |
| Petersen defect | mesenteric space behind Roux limb (internal hernia) |
| Plummer-Vinson | esophageal web with iron-deficiency anemia (Paterson-Kelly) |
| Peutz-Jeghers | hamartomatous polyposis with mucocutaneous pigmentation |
| Lynch syndrome | HNPCC, mismatch repair deficiency |
| Gardner / Turcot | FAP variants (desmoids-osteomas / CNS tumors) |
| Goodsall rule | anal fistula tract course prediction |
| Parks classification | anal fistula anatomy (intersphincteric, transsphincteric…) |
| Delorme / Altemeier | perineal mucosal sleeve resection / perineal rectosigmoidectomy for rectal prolapse |
| Ripstein procedure | anterior sling rectopexy |
| Bascom / Karydakis / Limberg | pilonidal flap procedures |
| Nigro protocol | chemoradiation for anal squamous cell carcinoma |
| Buschke-Löwenstein | giant condyloma acuminatum |
| Bowen disease | squamous cell carcinoma in situ |
| Paget disease (perianal/breast) | intraepithelial adenocarcinoma — distinguish from Paget bone disease |
| Fournier gangrene | perineal necrotizing fasciitis |
| Marjolin ulcer | carcinoma arising in chronic wound / burn scar |
| Lichtenstein repair | open tension-free mesh inguinal hernioplasty |
| McVay repair | Cooper ligament repair |
| Bassini / Shouldice | tissue (suture) inguinal repairs |
| TEP / TAPP | totally extraperitoneal / transabdominal preperitoneal laparoscopic repair |
| Rives-Stoppa | retromuscular (sublay) ventral hernia repair |
| TAR | transversus abdominis release |
| Richter hernia | partial-circumference (antimesenteric) bowel wall hernia |
| Littre / Amyand / De Garengeot | hernia containing Meckel / appendix (inguinal) / appendix (femoral) |
| Spigelian hernia | semilunar line hernia |
| Petit / Grynfeltt | inferior / superior lumbar triangle hernia |
| Howship-Romberg sign | obturator hernia medial thigh pain |
| Alvarado score | appendicitis clinical score |
| McBurney point | right lower quadrant appendiceal point |
| Rovsing sign | RLQ pain on LLQ palpation |
| Hinchey classification | perforated diverticulitis staging |
| Ranson criteria / Atlanta classification | pancreatitis severity scoring / classification |
| Child-Pugh / MELD | cirrhosis severity scores |
| Milan criteria | HCC transplant eligibility |
| Bismuth-Corlette | hilar cholangiocarcinoma classification |
| Strasberg classification | laparoscopic bile duct injury classification |
| Todani classification | choledochal cyst types |
| Couinaud segments / Cantlie line | liver segmental anatomy / principal plane |
| Pringle maneuver | hepatoduodenal ligament (portal triad) clamping |
| Kocher maneuver | duodenal mobilization |
| Cattell-Braasch / Mattox | right / left medial visceral rotation |
| Graham patch | omental patch of perforated ulcer |
| Cullen / Grey Turner sign | periumbilical / flank ecchymosis |
| Beck triad | tamponade: hypotension, distended neck veins, muffled heart sounds |
| Hamman sign | mediastinal crunch (pneumomediastinum) |
| Leriche syndrome | aortoiliac occlusive disease triad |
| Buerger disease | thromboangiitis obliterans |
| Takayasu arteritis | granulomatous large-vessel arteritis |
| Paget-Schroetter | effort thrombosis of axillosubclavian vein |
| May-Thurner | iliac vein compression syndrome |
| Fontaine / Rutherford | chronic limb ischemia classifications |
| Stanford / DeBakey | aortic dissection classifications |
| Crawford classification | thoracoabdominal aneurysm extent |
| NASCET criteria | carotid stenosis measurement method |
| Allen test | hand collateral (palmar arch) perfusion test |
| Virchow triad | stasis, endothelial injury, hypercoagulability |
| Wells / Caprini score | VTE probability / risk scores |
| CEAP | chronic venous disease classification |
| SMA syndrome (Wilkie) | vascular compression of the duodenum, superior mesenteric artery syndrome |
| Dunbar syndrome | median arcuate ligament syndrome, celiac compression |
| Mondor disease | superficial thrombophlebitis of the breast |
| Phyllodes tumor | cystosarcoma phyllodes |
| Stewart-Treves | lymphangiosarcoma in chronic lymphedema |
| Halsted / Patey mastectomy | radical / modified radical mastectomy |
| Poland syndrome | congenital chest wall-breast hypoplasia |
| Sistrunk procedure | thyroglossal duct cyst excision with hyoid |
| Berry ligament / tubercle of Zuckerkandl | thyroid-RLN surgical landmarks |
| Chvostek / Trousseau sign | hypocalcemia signs |
| Pemberton sign | thoracic inlet obstruction from goiter |
| von Recklinghausen | neurofibromatosis type 1 |
| von Hippel-Lindau | VHL syndrome (pheochromocytoma, RCC) |
| Wilms tumor | nephroblastoma |
| Meckel diverticulum | persistent omphalomesenteric (vitelline) duct |

(Do not guess eponyms not listed here — verify unfamiliar ones in the book.)

## UK ↔ US spelling (books are US — search the US form)

coeliac→celiac · oesophagus→esophagus · haemorrhage→hemorrhage ·
haemorrhoid→hemorrhoid · anaemia→anemia · caecum→cecum · oedema→edema ·
paediatric→pediatric · orthopaedic→orthopedic · anaesthesia→anesthesia ·
tumour→tumor · faecal→fecal · fistula-in-ano→anal fistula (also "fistula in ano") ·
diarrhoea→diarrhea · foetal→fetal · goitre→goiter · gynaecology→gynecology ·
ileo-anal→ileoanal · -ise→-ize verb endings · sulphur→sulfur ·
practise→practice · litre→liter · haematoma→hematoma · ischaemia→ischemia ·
septicaemia→septicemia · pyaemia→pyemia · leucocyte→leukocyte

## Possessive eponym note

Books vary between "Crohn's disease"/"Crohn disease", "Meckel's"/"Meckel",
"Hartmann's"/"Hartmann". BM25 tokenizes the apostrophe away in most cases, but
when a phrase search fails, retry without the possessive.
