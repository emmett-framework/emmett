# !/usr/bin/env python
# -*- coding: utf8 -*-
# Plural-Forms for en (English)

# English language has 2 forms: 1 singular and 1 plural
nplurals = 2


# Determine plural_id for number *n* as sequence of positive
# integers: 0,1,...
# NOTE! For singular form ALWAYS return plural_id = 0
get_plural_id = lambda n: int(n != 1)

# Construct and return plural form of *word* using
# *plural_id* (which ALWAYS>0). This function will be executed
# for words (or phrases) not found in plural_dict dictionary
construct_plural_form = lambda word, plural_id: (
                        word +  # NOQA
                            ('es'  # NOQA
                                if word[-1:] in ('s', 'x', 'o') or
                                word[-2:] in ('sh', 'ch')
                                else 's')
                        )  # NOQA
