from datetime import datetime


MOIS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}


def valider_resultat_ciment(data):
    """
    Validation métier du résultat obtenu par l'IA.
    """

    if not isinstance(data, dict):
        return False, "Résultat IA invalide"

    mois = data.get("mois")
    annee = data.get("annee")

    livraisons = data.get("livraisons_mois")
    cumul = data.get("cumul_annee")

    confiance = data.get("confiance")

    # --------------------------------------------------------
    # Mois
    # --------------------------------------------------------

    if not isinstance(mois, str):
        return False, "Mois absent"

    mois_normalise = mois.strip().lower()

    if mois_normalise not in MOIS:
        return False, f"Mois inconnu : {mois}"

    # --------------------------------------------------------
    # Année
    # --------------------------------------------------------

    if not isinstance(annee, int):
        return False, "Année invalide"

    if annee < 2000 or annee > datetime.now().year + 2:
        return False, f"Année suspecte : {annee}"

    # --------------------------------------------------------
    # Livraisons
    # --------------------------------------------------------

    if livraisons is None:
        return False, "Livraisons du mois absentes"

    if not isinstance(livraisons, (int, float)):
        return False, "Livraisons non numériques"

    if livraisons <= 0:
        return False, "Livraisons <= 0"

    # --------------------------------------------------------
    # Cumul
    # --------------------------------------------------------

    if cumul is not None:

        if not isinstance(cumul, (int, float)):
            return False, "Cumul non numérique"

        if cumul <= 0:
            return False, "Cumul <= 0"

        # Le cumul annuel doit normalement être >=
        # aux livraisons du mois.
        if cumul < livraisons:
            return False, (
                "Cumul annuel inférieur "
                "aux livraisons mensuelles"
            )

    # --------------------------------------------------------
    # Confiance
    # --------------------------------------------------------

    if confiance is None:
        return False, "Confiance absente"

    if not isinstance(confiance, (int, float)):
        return False, "Confiance invalide"

    if confiance < 0 or confiance > 1:
        return False, "Confiance hors intervalle"

    # Seuil volontairement élevé.
    if confiance < 0.80:
        return False, (
            f"Confiance trop faible : {confiance}"
        )

    return True, "Résultat valide"