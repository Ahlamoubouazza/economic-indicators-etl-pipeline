# 📊 Economic Indicators ETL Pipeline

An automated data engineering pipeline for collecting, transforming, storing and analyzing economic indicators from multiple heterogeneous data sources.

The project was developed during an engineering internship at the **Haut-Commissariat au Plan (HCP), Morocco** and focuses on automating the integration of economic data using Python, PostgreSQL, Apache Airflow and Docker.

## 🎯 Project Objectives

The main objectives of this project are to:

- Automate the collection of economic indicators from multiple sources.
- Process heterogeneous data from REST APIs, web pages and structured files.
- Clean, transform and validate collected data.
- Centralize historical observations in PostgreSQL.
- Automate and schedule ETL workflows with Apache Airflow.
- Provide structured data for analytical dashboards and reporting.

## 🏗️ Architecture

```text
        Data Sources
             │
     ┌───────┴────────┐
     │                │
 Maadialna        IMF PortWatch
 Web Source         REST API
     │                │
     └───────┬────────┘
             │
             ▼
       Python Extraction
             │
             ▼
    Cleaning & Transformation
             │
             ▼
        Data Validation
             │
             ▼
         PostgreSQL
             │
             ▼
         Power BI
             
      Apache Airflow
     Workflow Orchestration

           Docker
 Containerized Environment
```

## 🛠️ Technologies

- **Python** — data extraction, transformation and validation
- **Pandas** — data processing
- **Requests** — REST API integration
- **BeautifulSoup** — web data extraction
- **PostgreSQL** — centralized data storage
- **Apache Airflow 2.9.3** — workflow orchestration and scheduling
- **Docker / Docker Compose** — containerized execution environment
- **Power BI** — visualization and analytical dashboards
- **Git / GitHub** — version control

## 📡 Data Sources

### Maadialna

Data related to Moroccan dams and water resources is collected and transformed automatically.

The pipeline processes indicators such as:

- dam filling rates;
- water volumes;
- basin-level indicators;
- historical observations.

### IMF PortWatch

Port activity data is collected through the PortWatch ArcGIS REST API.

The pipeline handles:

- API requests;
- pagination;
- retries and connection failures;
- historical observations;
- import and export indicators;
- port calls and cargo activity.

## 🔄 ETL Workflow

The general workflow follows the traditional ETL process:

```text
EXTRACT
   │
   ▼
REST APIs / Web Sources / Files
   │
   ▼
TRANSFORM
   │
   ├── Cleaning
   ├── Normalization
   ├── Validation
   └── Historical processing
   │
   ▼
LOAD
   │
   ▼
PostgreSQL
   │
   ▼
Power BI
```

## ⏱️ Workflow Orchestration

Apache Airflow is used to automate and schedule the data pipelines.

The project contains dedicated DAGs for the main data sources:

```text
dags/
├── maadialna_dag.py
├── portwatch_dag.py
└── ciment_dag.py
```

Airflow coordinates the extraction, transformation and loading steps and provides execution monitoring.

## 🗄️ Data Model

The PostgreSQL database uses a dimensional model designed to centralize indicators from heterogeneous sources.

The main components include:

- indicator dimension;
- period dimension;
- source dimension;
- segment dimension;
- indicator value fact table.

This structure facilitates historical analysis and integration with Business Intelligence tools.

## 📁 Project Structure

```text
economic-indicators-etl-pipeline/
│
├── config/
├── dags/
│   ├── maadialna_dag.py
│   ├── portwatch_dag.py
│   └── ciment_dag.py
│
├── data/
├── docs/
├── pipeline/
├── sql/
├── src/
│   ├── ai/
│   ├── diagnostic/
│   ├── extract/
│   ├── load/
│   ├── pipeline/
│   ├── quality/
│   ├── transform/
│   └── validation/
│
├── tests/
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## 🔐 Environment Configuration

Sensitive credentials are not stored in the repository.

Create a local `.env` file based on:

```text
.env.example
```

Example:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=indicateurs_eco
DB_USER=postgres
DB_PASSWORD=your_password

AIRFLOW_SECRET_KEY=your_secret_key
AIRFLOW_DB_PASSWORD=your_airflow_db_password
AIRFLOW_ADMIN_PASSWORD=your_airflow_admin_password
```

The `.env` file is excluded from version control.

## 🐳 Running with Docker

The infrastructure can be launched using Docker Compose:

```bash
docker compose up -d
```

The environment includes:

- PostgreSQL database for economic indicators;
- PostgreSQL metadata database for Airflow;
- Apache Airflow Scheduler;
- Apache Airflow Webserver.

## 📊 Data Visualization

Processed data can be connected to **Power BI** for interactive analysis.

Dashboards were designed to analyze:

- dam filling rates and water volumes;
- historical evolution of indicators;
- Moroccan port activity;
- import and export activity;
- trends over time.

## 🎓 Project Context

This project was developed as part of an engineering internship at the **Haut-Commissariat au Plan (HCP), Morocco**.

It provided practical experience in:

- Data Engineering;
- ETL pipeline development;
- API integration;
- workflow orchestration;
- database modeling;
- data quality;
- containerization;
- Business Intelligence.

## 👩‍💻 Author

**Ahlam Oubouazza**  
Big Data & Artificial Intelligence Engineering Student  
Université EuroMed de Fès (UEMF)