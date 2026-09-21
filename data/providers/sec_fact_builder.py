class SECFactBuilder:
    def _find_concept(
        self,
        us_gaap,
        candidates
    ):

        best_selection = None
        best_entry = None

        for concept in candidates:

            fact = us_gaap.get(
                concept
            )

            if not isinstance(
                fact,
                dict
            ):
                continue

            units = fact.get(
                "units",
                {}
            )

            if not isinstance(
                units,
                dict
            ):
                continue

            for unit_name, entries in (
                units.items()
            ):

                if not isinstance(
                    entries,
                    list
                ):
                    continue

                latest_entry = (
                    self._select_latest_entry(
                        entries
                    )
                )

                if latest_entry is None:
                    continue

                if (
                    best_entry is None
                    or latest_entry.get(
                        "filed",
                        ""
                    )
                    > best_entry.get(
                        "filed",
                        ""
                    )
                ):

                    best_entry = (
                        latest_entry
                    )

                    best_selection = {
                        "concept":
                            concept,

                        "fact":
                            fact,

                        "unit":
                            unit_name,

                        "entry":
                            latest_entry
                    }
        return best_selection

# Find latest data
    def _select_latest_entry(
        self,
        entries
    ):

        if not isinstance(
            entries,
            list
        ):

            return None

        valid_entries = []

        for entry in entries:

            if not isinstance(
                entry,
                dict
            ):
                continue

            form = entry.get(
                "form"
            )

            filed = entry.get(
                "filed"
            )

            if form not in {
                "10-K",
                "10-Q"
            }:
                continue

            if not filed:
                continue

            valid_entries.append(
                entry
            )

        if not valid_entries:
            return None

        valid_entries.sort(
            key=lambda entry: (
                entry.get(
                    "filed",
                    ""
                ),
                entry.get(
                    "end",
                    ""
                ),
                entry.get(
                    "start",
                    ""
                )
            )
        )

        return valid_entries[-1]
    
    def build(
        self,
        company_facts
    ):

        result = {
            "entity_name": None,
            "cik": None,
            "facts": {}
        }

        if not isinstance(
            company_facts,
            dict
        ):

            return result

        result["entity_name"] = (
            company_facts.get(
                "entity_name"
            )
        )

        result["cik"] = (
            company_facts.get(
                "cik"
            )
        )

        facts = company_facts.get(
            "facts",
            {}
        )

        if not isinstance(
            facts,
            dict
        ):

            return result

        us_gaap = facts.get(
            "us-gaap",
            {}
        )

        if not isinstance(
            us_gaap,
            dict
        ):

            return result        
        fact_candidates = {
                "revenue": [
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "Revenues"
                ],

                "net_income": [
                    "NetIncomeLoss"
                ],

                "assets": [
                    "Assets"
                ],

                "liabilities": [
                    "Liabilities"
                ],

                "stockholders_equity": [
                    "StockholdersEquity"
                ],

                "cash": [
                    "CashAndCashEquivalentsAtCarryingValue",
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
                ],

                "operating_income": [
                    "OperatingIncomeLoss"
                ],

                "accounts_receivable": [
                    "AccountsReceivableNetCurrent"
                ],

                "accounts_payable": [
                    "AccountsPayableCurrent"
                ]
            }
        for (
                normalized_name,
                candidates
            ) in fact_candidates.items():

                selected = (
                    self._find_concept(
                        us_gaap,
                        candidates
                    )
                )

                if selected is None:
                    continue

                fact = selected[
                    "fact"
                ]

                unit_name = selected[
                    "unit"
                ]

                latest_entry = selected[
                    "entry"
                ]
                
                result["facts"][normalized_name] = {
                    "concept":
                        selected["concept"],

                    "label":
                        fact.get("label"),

                    "description":
                        fact.get(
                            "description"
                        ),

                    "unit":
                        unit_name,

                    "value":
                        latest_entry.get(
                            "val"
                        ),

                    "filed":
                        latest_entry.get(
                            "filed"
                        ),

                    "form":
                        latest_entry.get(
                            "form"
                        ),

                    "period_end":
                        latest_entry.get(
                            "end"
                        ),

                    "fiscal_year":
                        latest_entry.get(
                            "fy"
                        ),

                    "fiscal_period":
                        latest_entry.get(
                            "fp"
                        ),

                    "source":
                        "SEC"
                }  
        return result     

