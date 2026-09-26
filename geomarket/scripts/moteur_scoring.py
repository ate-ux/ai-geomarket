"""Moteur de scoring multicritere pondere pour AI GeoMarket.

Normalise les indicateurs par cellule (rangs percentiles), les agrege en
quatre axes ponderes (demande, accessibilite, attractivite, concurrence) et
produit un score de potentiel brut entre 0 et 100.

Les ponderations sont parametrables a l'execution : le module est importe par
les scripts suivants et par l'agent conversationnel.
"""
import json

import duckdb
import pandas as pd

POIDS_DEFAUT = {
    "demande": 0.40,
    "accessibilite": 0.25,
    "attractivite": 0.20,
    "concurrence": 0.15,
}

INDICATEURS = {
    "demande": ["dens_bat_km2", "dens_batie_m2_km2", "nb_education",
                "nb_sante", "nb_lieux_culte"],
    "accessibilite": ["dens_routiere_m_km2", "longueur_principale_m",
                      "nb_axes_structurants", "nb_transport"],
    "attractivite": ["dens_commerces_km2", "nb_commerces", "nb_restauration",
                     "nb_bureaux", "nb_loisirs"],
    "concurrence": ["nb_banques"],
}


def _percentile(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, method="average").fillna(0.0)


def charger_indicateurs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT * FROM indicateurs_cellules").df()


def calculer_scores(df: pd.DataFrame, poids: dict | None = None) -> pd.DataFrame:
    """Calcule les scores par axe et le potentiel brut (0 a 100)."""
    poids = {**POIDS_DEFAUT, **(poids or {})}
    total = sum(poids.values())
    if total <= 0:
        raise ValueError("La somme des ponderations doit etre positive")
    poids = {k: v / total for k, v in poids.items()}

    out = df.copy()
    for axe, cols in INDICATEURS.items():
        cols = [c for c in cols if c in out.columns]
        if not cols:
            out[f"score_{axe}"] = 0.0
            continue
        rangs = pd.concat([_percentile(out[c].astype(float)) for c in cols], axis=1)
        out[f"score_{axe}"] = rangs.mean(axis=1).round(4)

    potentiel = (
        poids["demande"] * out["score_demande"]
        + poids["accessibilite"] * out["score_accessibilite"]
        + poids["attractivite"] * out["score_attractivite"]
        - poids["concurrence"] * out["score_concurrence"]
    )
    plancher = -poids["concurrence"]
    out["score_potentiel_brut"] = (
        ((potentiel - plancher) / (1 - plancher)) * 100
    ).clip(0, 100).round(2)

    # Departage des ex aequo par densite batie puis identifiant de cellule : le
    # classement reste unique et stable lorsqu'il est presente a un decideur.
    out = out.sort_values(
        ["score_potentiel_brut", "dens_bat_km2", "cell_id"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    out["rang"] = range(1, len(out) + 1)
    return out


def ecrire_scores(con: duckdb.DuckDBPyConnection, df: pd.DataFrame,
                  table: str = "scores") -> None:
    con.register("_scores", df.drop(columns=[c for c in ("geom",) if c in df.columns]))
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _scores")
    con.unregister("_scores")


def run(poids: dict | None = None, table: str = "scores") -> pd.DataFrame:
    db = ("/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
          "/geomarket/db/geomarket.duckdb")
    con = duckdb.connect(db)
    con.execute("LOAD spatial;")
    df = calculer_scores(charger_indicateurs(con), poids)
    ecrire_scores(con, df, table)
    con.close()
    return df


if __name__ == "__main__":
    res = run()
    cols = ["rang", "arrondissement", "score_demande", "score_accessibilite",
            "score_attractivite", "score_concurrence", "score_potentiel_brut"]
    print("Top 15 des cellules par potentiel brut :")
    print(res[cols].head(15).to_string(index=False))
    print("\nDistribution du score :")
    print(res["score_potentiel_brut"].describe().round(2).to_string())
    print("\nMoyenne par arrondissement :")
    print(res.groupby("arrondissement")["score_potentiel_brut"].mean()
          .round(1).sort_values(ascending=False).to_string())
    with open("/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
              "/geomarket/outputs/poids_scoring.json", "w") as fh:
        json.dump(POIDS_DEFAUT, fh, indent=2)
