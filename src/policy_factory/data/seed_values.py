"""Pre-seeded Finnish national values for first-run initialization.

Each entry is a tuple of (filename, title, body_text).
These represent foundational values that transcend party lines —
factual and non-partisan.
"""

from __future__ import annotations

# (filename, title, body)
SEED_VALUES: list[tuple[str, str, str]] = [
    (
        "national-security.md",
        "National Security and Defence",
        (
            "Finland's national security is built on credible territorial defence, "
            "comprehensive security, and strong civil preparedness. Decades of "
            "military non-alignment gave way to NATO membership in 2023, reflecting "
            "a pragmatic reassessment of the security environment following Russia's "
            "full-scale invasion of Ukraine. Finland maintains one of Europe's largest "
            "trained reserves relative to population size, and defence spending "
            "consistently exceeds the NATO 2% of GDP guideline.\n\n"
            "National security extends beyond military defence to encompass "
            "cybersecurity, supply chain resilience, energy security, and the "
            "protection of critical infrastructure. Finland's 1,340-kilometre border "
            "with Russia makes eastern border security a permanent strategic concern."
        ),
    ),
    (
        "economic-prosperity.md",
        "Economic Prosperity and Competitiveness",
        (
            "Finland's economic model combines an open, export-oriented economy with "
            "a strong social safety net. Key sectors include technology and ICT, "
            "forest industry, clean energy, manufacturing, and an expanding services "
            "sector. Nokia's rise and transformation demonstrated both the potential "
            "and the risks of economic concentration.\n\n"
            "Maintaining competitiveness requires sustained investment in R&D, a "
            "skilled workforce, reasonable corporate taxation, and openness to "
            "international trade. Finland's small domestic market makes export "
            "success essential for prosperity, and the country's economic health "
            "depends heavily on the stability of global trade systems and EU "
            "internal market access."
        ),
    ),
    (
        "eu-membership.md",
        "EU Membership and European Solidarity",
        (
            "EU membership, gained in 1995, is a cornerstone of Finland's foreign "
            "and economic policy. The EU provides market access for Finnish exporters, "
            "a framework for coordinated foreign policy, and a collective voice on "
            "global issues including climate change, trade, and digital regulation.\n\n"
            "Finland has been a net contributor to the EU budget while benefiting "
            "from structural funds, research programmes (Horizon Europe), and the "
            "stability provided by eurozone membership. Finnish EU policy balances "
            "fiscal responsibility with solidarity, supporting the rule of law and "
            "democratic norms within the Union while advocating for budgetary "
            "discipline and efficient use of common resources."
        ),
    ),
    (
        "arctic-sovereignty.md",
        "Arctic Sovereignty and Interests",
        (
            "Finland is one of eight Arctic states and a founding member of the "
            "Arctic Council. While Finland lacks an Arctic coastline, its northernmost "
            "regions — Lapland — are firmly within the Arctic zone, and Arctic policy "
            "directly affects indigenous Sami communities, northern economic "
            "development, and environmental stewardship.\n\n"
            "Climate change is opening new shipping routes and resource extraction "
            "opportunities in the Arctic, increasing geopolitical competition. "
            "Finland's Arctic interests include sustainable development of northern "
            "regions, protection of Arctic ecosystems, rights of indigenous peoples, "
            "maintaining the Arctic as a zone of low tension, and leveraging Finnish "
            "expertise in cold-climate technology, icebreaking, and Arctic logistics."
        ),
    ),
    (
        "democratic-institutions.md",
        "Democratic Institutions and Rule of Law",
        (
            "Finland consistently ranks among the world's strongest democracies in "
            "international indices (Freedom House, Economist Intelligence Unit, V-Dem). "
            "The country's democratic foundations rest on an independent judiciary, "
            "free press, transparent governance, low corruption, and robust "
            "parliamentary oversight.\n\n"
            "Protecting democratic institutions requires vigilance against both "
            "domestic erosion and external interference. Disinformation campaigns, "
            "hybrid threats targeting public trust, and the global trend of "
            "democratic backsliding all demand active defence of democratic norms. "
            "Finland's high social trust — among the highest in the world — is both "
            "a democratic asset and a resource that must be actively maintained "
            "through institutional integrity and civic education."
        ),
    ),
    (
        "social-welfare.md",
        "Social Welfare and Equality",
        (
            "The Nordic welfare model is central to Finnish society. Universal "
            "healthcare, comprehensive social insurance, income-related pensions, "
            "and generous parental leave policies provide a safety net that reduces "
            "poverty and inequality. Finland's Gini coefficient is among the lowest "
            "in the OECD, reflecting relatively equitable income distribution.\n\n"
            "Maintaining the welfare state faces demographic challenges: an ageing "
            "population, low birth rates, and growing healthcare costs pressure "
            "public finances. Gender equality, while advanced by global standards, "
            "requires continued attention in areas such as pay equity, care "
            "responsibilities, and representation in corporate leadership. The "
            "integration of immigrants into the labour market and society is an "
            "increasingly important dimension of social policy."
        ),
    ),
    (
        "technological-competitiveness.md",
        "Technological Competitiveness and Innovation",
        (
            "Finland has a strong tradition of technology innovation, from Nokia's "
            "mobile revolution to leadership in 5G/6G research, AI, and quantum "
            "computing. The country ranks highly in digital public services, internet "
            "penetration, and STEM education. Finnish universities and research "
            "institutions — particularly VTT, Aalto University, and the University "
            "of Helsinki — are globally competitive.\n\n"
            "Sustaining technological leadership requires strategic R&D investment "
            "(Finland targets 4% of GDP), attracting and retaining international "
            "talent, fostering startup ecosystems, and making strategic bets on "
            "emerging technologies. Digital sovereignty — the ability to control "
            "critical technology infrastructure and avoid excessive dependency on "
            "non-European platforms — is an emerging policy concern."
        ),
    ),
    (
        "cultural-identity.md",
        "Cultural Identity and Heritage",
        (
            "Finnish cultural identity is shaped by a distinctive linguistic heritage "
            "(Finnish and Swedish as national languages, plus Sami languages), a "
            "strong connection to nature, the sauna tradition, and values of "
            "self-reliance (sisu), modesty, and honesty. Finland's cultural "
            "institutions — libraries, public broadcasting (Yle), education "
            "system — play a vital role in maintaining cultural continuity.\n\n"
            "Cultural policy must balance preservation of heritage with openness "
            "to a diversifying society. Immigration is changing Finland's cultural "
            "landscape, creating both enrichment and integration challenges. "
            "Protecting minority languages and cultures (Swedish-speaking Finns, "
            "Sami, Roma) while fostering a shared civic identity is an ongoing "
            "balancing act. The creative industries — gaming (Supercell, Remedy), "
            "design, music — are also significant cultural exports."
        ),
    ),
    (
        "environmental-sustainability.md",
        "Environmental Sustainability and Climate Action",
        (
            "Finland has committed to carbon neutrality by 2035, one of the most "
            "ambitious targets globally. The country's energy mix is already heavily "
            "decarbonised through nuclear power, hydroelectricity, biomass, and "
            "growing wind capacity. The Olkiluoto 3 reactor, commissioned in 2023, "
            "significantly boosted low-carbon electricity generation.\n\n"
            "Environmental policy must balance climate ambition with economic "
            "competitiveness and social fairness. The forest industry — a major "
            "economic sector and carbon sink — sits at the intersection of economic, "
            "environmental, and biodiversity concerns. Finland's extensive forests "
            "(over 70% of land area) are both an economic resource and a critical "
            "carbon reservoir. Biodiversity loss, water quality in the Baltic Sea, "
            "and sustainable land use are additional environmental priorities."
        ),
    ),
    (
        "education-research.md",
        "Education and Research Excellence",
        (
            "Finland's education system is internationally renowned for equity, "
            "quality, and the high status of the teaching profession. The PISA "
            "results consistently place Finland among top performers, though recent "
            "trends show some decline that has prompted policy attention. Education "
            "is publicly funded from pre-primary through university, with no tuition "
            "fees for EU/EEA students.\n\n"
            "Research excellence is concentrated in a network of universities and "
            "research institutes, with the Academy of Finland and Business Finland "
            "providing strategic research funding. Challenges include maintaining "
            "research funding levels, competing globally for talent, ensuring "
            "education adapts to technological change (AI literacy, digital skills), "
            "and bridging the gap between research and commercial application. "
            "Lifelong learning and vocational education are critical for workforce "
            "adaptability in a rapidly changing economy."
        ),
    ),
]
