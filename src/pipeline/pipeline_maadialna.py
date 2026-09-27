import logging

from src.transform.transform_maadialna import transform_maadialna
from src.transform.transform_national_maadialna import (
    transform_national_maadialna
)
from src.load.load_maadialna import load_historical
from src.load.load_postgresql_maadialna import load_maadialna

# ============================================
# CONFIGURATION DES LOGS
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ============================================
# PIPELINE MAADIALNA
# ============================================

def run_pipeline():

    logger.info("=" * 60)
    logger.info("🚀 DÉMARRAGE DU PIPELINE MAADIALNA")
    logger.info("=" * 60)

    try:

        # ====================================
        # ÉTAPE 1 : EXTRACTION + TRANSFORMATION
        # DES BARRAGES
        # ====================================

        logger.info(
            "📥 Étape 1 : extraction et transformation des barrages"
        )

        df_barrages = transform_maadialna()

        df_barrages.to_csv(
            "data/barrages.csv",
            index=False,
            encoding="utf-8-sig"
        )

        logger.info(
            "✅ Fichier data/barrages.csv créé : %s lignes",
            len(df_barrages)
        )

        # ====================================
        # ÉTAPE 2 : EXTRACTION + TRANSFORMATION
        # DES DONNÉES NATIONALES
        # ====================================

        logger.info(
            "📥 Étape 2 : extraction et transformation des données nationales"
        )

        df_national = transform_national_maadialna()

        df_national.to_csv(
            "data/national_barrages.csv",
            index=False,
            encoding="utf-8-sig"
        )

        logger.info(
            "✅ Fichier data/national_barrages.csv créé : %s ligne(s)",
            len(df_national)
        )

        # ====================================
        # ÉTAPE 3 : MISE À JOUR DE L'HISTORIQUE
        # DES BARRAGES
        # ====================================

        logger.info(
            "📚 Étape 3 : vérification de l'historique des barrages"
        )

        changed_barrages = load_historical(
            "data/barrages.csv",
            "data/historique_barrages.csv"
        )

        if changed_barrages:
            logger.info(
                "🔄 Les données des barrages ont changé"
            )
        else:
            logger.info(
                "⏭️ Les données des barrages sont identiques"
            )

        # ====================================
        # ÉTAPE 4 : MISE À JOUR DE L'HISTORIQUE
        # DES DONNÉES NATIONALES
        # ====================================

        logger.info(
            "📚 Étape 4 : vérification de l'historique national"
        )

        changed_national = load_historical(
            "data/national_barrages.csv",
            "data/history_national_barrages.csv"
        )

        if changed_national:
            logger.info(
                "🔄 Les données nationales ont changé"
            )
        else:
            logger.info(
                "⏭️ Les données nationales sont identiques"
            )

        # ====================================
        # ÉTAPE 5 : CHARGEMENT POSTGRESQL
        # ====================================

        if changed_barrages or changed_national:

            logger.info(
                "🐘 Étape 5 : changement détecté, chargement dans PostgreSQL"
            )

            load_maadialna(
                barrages_path="data/historique_barrages.csv",
                national_path="data/history_national_barrages.csv"
            )

            logger.info(
                "✅ Chargement PostgreSQL terminé"
            )

        else:
            logger.info(
                "⏭️ Étape 5 ignorée : aucun changement détecté"
            )

        # ====================================
        # FIN DU PIPELINE
        # ====================================

        logger.info("=" * 60)
        logger.info("🎉 PIPELINE MAADIALNA TERMINÉ AVEC SUCCÈS")
        logger.info("=" * 60)

    except Exception:
        logger.exception(
            "❌ ERREUR : le pipeline Maadialna a échoué"
        )
        raise

# ============================================
# EXECUTION
# ============================================

if __name__ == "__main__":
    run_pipeline()