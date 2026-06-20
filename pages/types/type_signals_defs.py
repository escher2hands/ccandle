SIGNAL_KEYS = [
    # base_content_signals
    'word_count', 'image_count', 'image_density', 'task_count', 'mentions_count', 'mention_density',
    'diagram_count', 'bullet_count', 'header_count', 'digit_to_letter_ratio',
    # paragraph signals
    'para_count', 'para_longest', 'para_share_long', 'para_share_short', 'para_average',
    'para_lead_good', 'para_lead_words', 'para_lead_links',
    # connectedness signals
    'link_count', 'link_git_count', 'link_jira_count', 'link_density', 'child_count',
    # aggregate table signals
    'table_count', 'minutes_in_tables', 'word_count_outside_tables',
    'diagram_outside_tables', 'img_outside_tables',
    'sig_table_has_cells', 'sig_cell_share_low_words', 'sig_cell_share_empty',
    'sig_table_long_cell', 'sig_cell_many',
    # aggregate lexicographic signals
    'lexic_jargon_share', 'lexic_rare_words_share', 'lexic_topical_focus',
    # aggregate macro signals
    'macro_toc', 'macro_jira_query',
    'macro_struct_total', 'macro_panels', 'macro_expandables', 'macro_excerpts', 'macro_decisions', 'macro_children',
    # code block signals
    'code_blocks', 'code_blocks_lines',
    # keywords in titles / body / headers signals
    't_month', 't_g_meeting_minutes', 't_meeting_minutes', 't_g_workshop_minutes', 't_workshop_minutes',
    't_release', 't_performance', 't_anti_landing', 't_intro', 't_anti_intro', 't_solution',
    'h_solution',
    'b_meeting_minutes', 'b_workshop', 'b_g_release', 'b_release', 'b_anti_release', 'b_performance',
    'b_anti_performance', 'b_bug',
    # title has date signals
    'date', 'date_bad', 'date_reverse',
    # metric flags signals
    'metric_flags',
]

SIGNALS_VECTOR_DIM = 70
