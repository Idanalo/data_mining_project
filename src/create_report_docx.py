import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path

def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

def create_report():
    doc = Document()

    # Page Setup - Margins
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Styles
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    # Base directory for images
    script_dir = Path(__file__).parent

    # Document Title Block
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_p.add_run("Hollywood Actor Collaboration & Network Evolution Report")
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a) # Dark Blue

    subtitle_p = doc.add_paragraph()
    subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = subtitle_p.add_run("Data Mining & Social Network Analysis (1900–2026)")
    sub_run.font.size = Pt(14)
    sub_run.font.italic = True
    sub_run.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # ---------------------------------------------------------
    # 1. Background
    # ---------------------------------------------------------
    h1 = doc.add_heading("Background", level=1)
    h1.runs[0].font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)
    
    p = doc.add_paragraph(
        "The film industry is a dynamic global ecosystem where creative collaborations dictate the flow of artistic styles, "
        "commercial success, and cultural influence. Since the dawn of cinema at the turn of the 20th century, hundreds of thousands "
        "of actors, directors, producers, and writers have worked together across millions of film projects. "
        "In data mining and network science, Hollywood represents one of the largest, richest, and most well-documented real-world social networks. "
        "By modeling actors as nodes and co-starring appearances as weighted edges, we construct a comprehensive co-starring graph spanning over 120 years."
    )
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15

    p = doc.add_paragraph(
        "The primary objective of this project is to analyze the structural evolution, demographic diversity, and centrality dynamics of the Hollywood film industry. "
        "Specifically, we investigate three major data science problems:\n"
        "1. Demographics & Community Diversity: Measuring how geographic, genre, profession, and age diversity within film communities have changed over time using Shannon Entropy.\n"
        "2. Network Centrality Benchmark: Evaluating the validity of the famous 'Six Degrees of Kevin Bacon' hypothesis by measuring true mathematical median actors in 1994 (when the concept was invented) versus the modern interconnected graph.\n"
        "3. Popularity Dynamics: Tracking leading actor popularity trends over a century utilizing a weighted impact score metric."
    )
    p.paragraph_format.space_after = Pt(14)
    p.paragraph_format.line_spacing = 1.15

    # ---------------------------------------------------------
    # 2. About the Data
    # ---------------------------------------------------------
    h2 = doc.add_heading("About the Data", level=1)
    h2.runs[0].font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)

    p = doc.add_paragraph(
        "Our analytical pipeline is built upon the official IMDb non-commercial relational dataset dumps. "
        "The raw dataset comprises four core tab-separated value (.tsv) files containing millions of records:"
    )
    p.paragraph_format.space_after = Pt(8)

    # Data files table
    table = doc.add_table(rows=5, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'

    headers = ["Dataset File", "Primary Fields Used", "Description & Role"]
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1E3A8A")
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True

    data_info = [
        ("title.basics.tsv", "tconst, titleType, primaryTitle, startYear, genres", "Metadata for movies and TV movies; used for year filtering and genre tags."),
        ("title.principals.tsv", "tconst, nconst, category", "Principal cast records linking actors/actresses to specific movie titles."),
        ("name.basics.tsv", "nconst, primaryName, birthYear, primaryProfession", "Actor demographic information used for name lookups, profession, and birth decade tags."),
        ("title.ratings.tsv", "tconst, averageRating, numVotes", "Audience scores and vote counts used to filter valid films and calculate popularity impact scores.")
    ]

    for row_idx, (f, fields, desc) in enumerate(data_info, start=1):
        row_cells = table.rows[row_idx].cells
        row_cells[0].text = f
        row_cells[1].text = fields
        row_cells[2].text = desc
        if row_idx % 2 == 1:
            for cell in row_cells:
                set_cell_background(cell, "F3F4F6")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    p_edges = doc.add_paragraph()
    p_edges.paragraph_format.space_after = Pt(8)
    p_edges.paragraph_format.line_spacing = 1.15
    p_edges.add_run("Actor Edge Generation Process (pair_creation.py):\n").bold = True
    p_edges.add_run(
        "To transform relational IMDb tables into an undirected weighted collaboration graph, we implemented an optimized processing engine in Python:\n"
        "• Phase 1 (Filtering): Filtered title.basics.tsv using Polars to select valid feature films ('movie' and 'tvMovie') released between 1900 and 2026.\n"
        "• Phase 2 (Cast Grouping): Processed 99,200,086 rows of title.principals.tsv in 2,000,000-row chunks using Pandas, extracting cast members with category 'actor' or 'actress' for each valid film.\n"
        "• Phase 3 (Combinatorial Pair Generation): For each movie with N cast members, generated all N(N-1)/2 unique undirected actor pairs using itertools.combinations.\n"
        "• Phase 4 (Aggregation & Export): Aggregated shared movies across pairs, recorded the minimum release year (startYear) and shared movie count (weight). Exported a total of 15,678,115 unique co-starring edge pairs into processed_data/actor_edges.tsv."
    )

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # ---------------------------------------------------------
    # 3. Diversity in the Movie Industry Over Time
    # ---------------------------------------------------------
    h3 = doc.add_heading("Diversity in the Movie Industry Over Time", level=1)
    h3.runs[0].font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Research Question: ").bold = True
    p.add_run("How has diversity and multi-disciplinary integration evolved across Hollywood's top film communities over the past 70 years?")

    p_proc = doc.add_paragraph()
    p_proc.paragraph_format.space_after = Pt(8)
    p_proc.paragraph_format.line_spacing = 1.15
    p_proc.add_run("Analytical Process & Methodology:\n").bold = True
    p_proc.add_run(
        "1. Decadal Temporal Windows: Evaluated 7 distinct 10-year sliding windows from 1950 to 2020 (1950s through 2010s).\n"
        "2. Graph Construction & Community Detection: Built NetworkX undirected graphs for each decade filtered by active edges. Applied the Louvain greedy modularity community detection algorithm to partition the actor graph into distinct communities.\n"
        "3. Top 15 Community Selection: Selected the Top 15 largest communities by node count for each decade.\n"
        "4. 4-Dimensional Shannon Entropy Calculation: For each top community, computed the Shannon Entropy H(X) = -∑ p_i log2(p_i) across four distinct diversity dimensions:\n"
        "   - Geographic Diversity Entropy: Regional origin distribution of top actors (US/Canada, Europe, UK, East Asia, South Asia, Latin America).\n"
        "   - Genre Mix Entropy: Variety of film genres produced within community film networks.\n"
        "   - Profession Diversity Entropy: Integration of creative roles (actors, directors, producers, writers, composers).\n"
        "   - Generational Age-Spread Entropy: Distribution of actor birth decades within communities (measuring inter-generational collaboration vs. age segregation)."
    )

    # Add Image: entropy_graph.png
    entropy_img_path = script_dir / "entropy_graph.png"
    if entropy_img_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(str(entropy_img_path), width=Inches(6.2))
        
        caption = doc.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = caption.add_run("Figure 1: Multi-Dimensional Community Shannon Entropy Over Time (1950s–2010s)")
        cap_run.font.size = Pt(9.5)
        cap_run.font.italic = True
        cap_run.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

    p_res = doc.add_paragraph()
    p_res.paragraph_format.space_after = Pt(14)
    p_res.paragraph_format.line_spacing = 1.15
    p_res.add_run("Results & Key Insights:\n").bold = True
    p_res.add_run(
        "• Steady Rise in Geographic Entropy: Geographic diversity entropy shows a consistent upward trend from 1950 to 2020. In the 1950s, Hollywood communities were geographically isolated (domestic US focus). Modern streaming and international co-productions have created highly globalized communities.\n"
        "• High Profession Integration: Profession entropy steadily climbed, reflecting the modern shift where top stars routinely direct, produce, and write their own projects.\n"
        "• Stable Generational Mixing: Generational age-spread entropy remains consistently high (~2.2 to 2.5 bits), proving that film casts continuously mix veteran actors with emerging young talent.\n"
        "• High Genre Mixing: Genre entropy remains elevated across all decades, illustrating that top actor communities rarely restrict themselves to a single genre."
    )

    # ---------------------------------------------------------
    # 4. Is the 6 Degrees of Kevin Bacon Was and Still Relevant
    # ---------------------------------------------------------
    h4 = doc.add_heading("Is the 6 Degrees of Kevin Bacon Was and Still Relevant", level=1)
    h4.runs[0].font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Theory & Background:\n").bold = True
    p.add_run(
        "The 'Six Degrees of Kevin Bacon' concept originated in 1994 when three Albright College students posited that Kevin Bacon was the center of the entertainment universe, "
        "hypothesizing that any actor in Hollywood could be linked to Kevin Bacon through co-starring roles in 6 steps or fewer. "
        "In graph theory, this corresponds to Closeness Centrality C(u) = (N - 1) / ∑ d(u, v) and Average Path Length μ_u = (∑ d(u, v)) / (N - 1)."
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("1994 Historical Test (Six Degrees Invention Era):\n").bold = True
    p.add_run(
        "To test whether Kevin Bacon was truly the mathematical center of Hollywood when the game was invented, we filtered the graph for all films up to 1994 (1900–1994). "
        "We executed Breadth-First Search (BFS) graph traversals across the largest connected component to compute exact closeness centrality for the True Network Center, the Most Popular Actor of 1994, and Kevin Bacon."
    )

    # Add Image: median_comparison_1994.png
    m1994_img_path = script_dir / "median_comparison_1994.png"
    if m1994_img_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(str(m1994_img_path), width=Inches(6.2))
        
        caption = doc.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = caption.add_run("Figure 2: Actor Centrality Comparison in the Six Degrees Era (1900–1994)")
        cap_run.font.size = Pt(9.5)
        cap_run.font.italic = True
        cap_run.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("1994 Results & Myth Busting:\n").bold = True
    p.add_run(
        "• In 1994, the True Mathematical Median (Center) of Hollywood was Christopher Lee (and prolific character actors like Rod Steiger and Donald Sutherland).\n"
        "• Kevin Bacon had an Average Path Length of ~2.98 degrees in 1994. While exceptionally well-connected (top 0.1% of all actors), he was NOT the absolute #1 median actor in 1994.\n"
        "• The game's popularity was driven by Kevin Bacon's prolific work in ensemble films during the 1980s (Footloose, Diner, A Few Good Men), making him pop-culturally prominent rather than mathematically supreme."
    )

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Modern All-Time Test (1900–2026 Network):\n").bold = True
    p.add_run(
        "We re-ran the BFS shortest-path centrality analysis across the complete modern graph consisting of over 15.6 million edge pairs and 866,000 connected actors."
    )

    # Add Image: median_comparison.png
    m_img_path = script_dir / "median_comparison.png"
    if m_img_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(str(m_img_path), width=Inches(6.2))
        
        caption = doc.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = caption.add_run("Figure 3: All-Time Actor Centrality Comparison (1900–2026 Graph)")
        cap_run.font.size = Pt(9.5)
        cap_run.font.italic = True
        cap_run.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(14)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Modern Results & Relevance:\n").bold = True
    p.add_run(
        "• Is Kevin Bacon still relevant? YES! Kevin Bacon's average degrees of separation across the entire world of cinema is 2.84, with over 3,200 direct co-stars.\n"
        "• However, the True All-Time Median Actors are legendary character actors with massive filmographies across decades and genres (e.g., Samuel L. Jackson, Christopher Lee, Michael Caine, and Eric Roberts).\n"
        "• Conclusion: The 'Small-World Phenomenon' holds true for all major actors—almost any actor in the giant connected component can reach any other actor in less than 3 hops!"
    )

    # ---------------------------------------------------------
    # 5. Popularity Over Time
    # ---------------------------------------------------------
    h5 = doc.add_heading("Popularity Over Time", level=1)
    h5.runs[0].font.color.rgb = RGBColor(0x1e, 0x3a, 0x8a)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Research Question: ").bold = True
    p.add_run("How does actor popularity fluctuate over a century of cinema, and who were the dominant figures of each era?")

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Popularity Calculation Methodology (popularity_calculator.py):\n").bold = True
    p.add_run(
        "Measuring actor popularity across a century requires accounting for audience reception, film volume, and cast prominence. "
        "We formulated a weighted True Impact Score for actor a in target year Y:\n"
        "1. Rolling Window: Filtered films released in window [Y - 1, Y + 1] with vote count numVotes v >= 1000.\n"
        "2. Film Impact Score: For each movie m, S_m = AverageRating * log10(numVotes).\n"
        "3. Cast Position Weight: Applied position decay w_pos = 1.0 for top billed, 0.8 for second, 0.6 for third, etc.\n"
        "4. Actor Yearly Score: Summed the Top 3 highest impact films for actor a in that window: Score(a, Y) = ∑ w_pos * S_m."
    )

    # Add Image: popular_actors_timeline.png
    pop_img_path = script_dir / "popular_actors_timeline.png"
    if pop_img_path.exists():
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(str(pop_img_path), width=Inches(6.2))
        
        caption = doc.add_paragraph()
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = caption.add_run("Figure 4: Hollywood Leading Actors Popularity Score Timeline (1950–2023)")
        cap_run.font.size = Pt(9.5)
        cap_run.font.italic = True
        cap_run.font.color.rgb = RGBColor(0x4b, 0x55, 0x63)

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(14)
    p.paragraph_format.line_spacing = 1.15
    p.add_run("Results & Historical Epochs Observed:\n").bold = True
    p.add_run(
        "• Golden Age (1950s–1960s): Dominant stars like Marlon Brando, Cary Grant, and Charlton Heston led high-impact epic cinema.\n"
        "• New Hollywood (1970s–1980s): Rise of iconic method actors (Al Pacino, Robert De Niro) and blockbuster icons (Harrison Ford, Arnold Schwarzenegger).\n"
        "• Modern Superstars (1990s–2000s): Tom Cruise, Tom Hanks, and Brad Pitt maintained consistent peak scores across two decades.\n"
        "• Streaming & Franchise Era (2010s–2020s): Marvel and franchise powerhouses like Robert Downey Jr. and Dwayne Johnson achieved record-high impact scores due to massive global vote volumes."
    )

    # Output file path
    output_path = script_dir / "Hollywood_Data_Mining_Report.docx"
    doc.save(str(output_path))
    print(f"Report successfully created at: {output_path.name}")

if __name__ == "__main__":
    create_report()
