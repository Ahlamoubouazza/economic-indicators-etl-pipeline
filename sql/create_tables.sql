-- ============================================
-- DIMENSIONS
-- ============================================

CREATE TABLE dim_source (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(150) NOT NULL,
    type_source VARCHAR(30) NOT NULL,
    niveau_fiabilite VARCHAR(30) NOT NULL
);

CREATE TABLE dim_indicateur (
    id SERIAL PRIMARY KEY,
    code VARCHAR(80) UNIQUE NOT NULL,
    nom VARCHAR(200) NOT NULL,
    categorie VARCHAR(50) NOT NULL,
    unite VARCHAR(30) NOT NULL
);

CREATE TABLE dim_periode (
    id SERIAL PRIMARY KEY,
    date_reference DATE UNIQUE NOT NULL,
    annee INT NOT NULL,
    mois INT NOT NULL,
    trimestre INT NOT NULL
);

CREATE TABLE dim_segment (
    id SERIAL PRIMARY KEY,
    type_segment VARCHAR(30) NOT NULL,
    code VARCHAR(80) NOT NULL,
    libelle VARCHAR(200) NOT NULL,
    UNIQUE (type_segment, code)
);

-- ============================================
-- TABLE DE FAITS
-- ============================================

CREATE TABLE fait_indicateur_valeur (
    id SERIAL PRIMARY KEY,
    indicateur_id INT NOT NULL REFERENCES dim_indicateur(id),
    periode_id INT NOT NULL REFERENCES dim_periode(id),
    source_id INT NOT NULL REFERENCES dim_source(id),
    segment_id INT REFERENCES dim_segment(id),
    valeur NUMERIC NOT NULL,
    statut VARCHAR(20) NOT NULL CHECK (statut IN ('provisoire', 'revise', 'consolide')),
    date_extraction TIMESTAMP NOT NULL DEFAULT now(),
    valide_depuis TIMESTAMP NOT NULL DEFAULT now(),
    valide_jusqu_a TIMESTAMP,
    est_courante BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_fait_courant ON fait_indicateur_valeur (indicateur_id, periode_id, segment_id)
    WHERE est_courante = TRUE;
CREATE INDEX idx_fait_source ON fait_indicateur_valeur (source_id);