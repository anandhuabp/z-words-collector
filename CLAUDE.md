Of course. Here is a comprehensive project document that synthesizes our entire discussion, including your latest revisions. This document is designed to provide a complete context for any developer or AI assistant, like the Gemini CLI, to understand the project's goals, architecture, and implementation plan.

-----

# Project Documentation: "Z-Words Collector"

## 1\. Project Mission & Vision

**Mission:** To create a robust, scalable, and automated system for collecting, archiving, and analyzing data from Russian propaganda channels (primarily on Telegram). The goal is to provide a valuable dataset for historical analysis, journalistic investigations, and machine learning research into the nature of modern propaganda.

**Core Vision:** The project is built on a modular "data pipeline" architecture, designed to evolve from a simple MVP into a powerful platform with a flexible API, a user interface for researchers, and advanced data processing capabilities.

## 2\. High-Level Architecture

The system is designed around four distinct layers, ensuring modularity and scalability.

1.  **Data Ingestion:** Responsible for automatically collecting raw data from sources like Telegram.
2.  **Data Storage:** A flexible storage layer designed to handle large volumes of text, media, and metadata.
3.  **Data Processing:** Enriches the raw data through tagging, entity extraction, and sentiment analysis.
4.  **Data Access:** Provides access to the processed data via a secure API and a web interface.

While the long-term vision includes technologies like PostgreSQL, Elasticsearch, and Neo4j, the initial implementation focuses on a pragmatic and robust **Minimum Viable Product (MVP)**.

## 3\. MVP Implementation Plan

The MVP focuses on creating a reliable, automated data collection pipeline that runs on a single server using Docker and is managed via GitHub Actions.

### \#\#\# Component 1: The Parser Script (`parser.py`)

This is the core data ingestion component, a Python script using the **Telethon** library.

  * **Core Logic (Incremental Updates):**
      * The script is idempotent. It maintains state by checking the `index.json` file for the last known post ID (`last_known_id`) for each channel.
      * For subsequent runs, it fetches only new messages using Telethon's `min_id` parameter, ensuring no duplicates are downloaded and API usage is minimized.
  * **Initial Run (Backfill):**
      * For new channels, the script performs a historical backfill.
      * To prevent timeouts, the backfill is performed in **chunks** (e.g., 1000 messages at a time) using `offset_id`.
      * A **minimum date** (e.g., `2022-01-24`) is used as a cutoff to avoid fetching irrelevant ancient history. If the channel was created after this date, its creation date is used as the starting point.
  * **Error Handling & Reliability:**
      * The script includes robust **error handling** for network issues and Telegram API rate limits, utilizing exponential backoff strategies.
      * Failures are logged. If a run fails, the next scheduled run will automatically retry fetching data from the `last_known_id`.
      * **Gap Detection:** After a fetch, the script can perform a basic check for sequential gaps in message IDs. Gaps are logged, as they often indicate that posts have been deleted by channel administrators.

### \#\#\# Component 2: Data Storage & Organization

The MVP uses a structured file system on the server, which can be easily migrated to a cloud object store (like AWS S3) in the future.

  * **Directory Structure:** Data is organized hierarchically for easy management.
    ```
    project_root/
    ├── data/
    │   └── channel_username/
    │       ├── index.json
    │       └── 2025-10-14.json.gz
    │       └── 2025-10-15.json.gz
    │
    ├── session/
    │   └── my_telegram_session.session
    ...
    ```
  * **File Format:**
      * Data is stored in **compressed JSON files** (`.json.gz`) to save space. Each file contains a list of posts collected on that day.
      * The script saves the **raw Telethon message object** (converted to a dictionary) to preserve all available information, including text, metadata, and `entities` (links, mentions, formatting).
      * Each JSON file contains a `metadata` header with information about the collection batch (e.g., `collection_timestamp`, `min_id_in_batch`, `max_id_in_batch`).
  * **State Management (`index.json`):**
      * Each channel directory contains a master `index.json` file.
      * This file is the "source of truth" for the state of the archive, containing metadata like `total_posts_archived`, `last_known_id`, and a list of all data files.
      * The parser script reads this file at the start of each run to determine its starting point, making the process fast and efficient.

### \#\#\# Component 3: Containerization (Docker)

The entire application is containerized using Docker and Docker Compose for portability, dependency management, and easy deployment.

  * **`Dockerfile`:** Defines the environment for the Python script, installing dependencies from `requirements.txt`.
    ```dockerfile
    # Use an official lightweight Python image
    FROM python:3.10-slim

    # Set the working directory inside the container
    WORKDIR /app

    # Copy the dependencies file and install them
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy the application script into the container
    COPY parser.py .

    # Specify the command to run on container startup
    CMD ["python", "parser.py"]
    ```
  * **`docker-compose.yml`:** Orchestrates the service, linking the container to the host file system for data persistence.
    ```yaml
    version: '3.8'

    services:
      parser:
        build: .
        # Load environment variables from the .env file
        env_file:
          - .env
        # Mount host directories into the container for data persistence
        volumes:
          - ./data:/app/data
          - ./session:/app/session
    ```

### \#\#\# Component 4: Automation (GitHub Actions)

CI/CD is handled by GitHub Actions, enabling automated, scheduled data collection.

  * **Workflow Triggers:** The workflow is triggered on a schedule (`cron`) and can also be triggered manually from the GitHub UI (`workflow_dispatch`).
  * **Secret Management:** Sensitive credentials (`API_ID`, `API_HASH`, `PHONE_NUMBER`) are stored as **GitHub Actions Secrets**. During the workflow run, they are securely passed to the server to create a `.env` file just before the script executes.
  * **Deployment Logic:** The workflow connects to the server via SSH, pulls the latest code from the repository, builds the Docker image if necessary, and runs the parser using `docker-compose`.
  * **Notifications:** Upon job failure, an automated notification is sent to a designated channel (e.g., a private Telegram chat) using a webhook, ensuring immediate awareness of any collection issues.
  * **Security:** The `*.session` file, which contains authentication credentials, is stored on the server in the `session/` volume and is explicitly listed in `.gitignore` to prevent it from ever being committed to the repository.

## 4\. Future Vision (Post-MVP)

Upon successful implementation of the MVP, the project will evolve by developing the remaining architectural layers:

  * **Storage:** Migrate from the file system to a **PostgreSQL** database for structured data and relational queries. Set up **Elasticsearch** for advanced full-text search and **Neo4j** or `pgvector` for analyzing relationships (reposts, links) and semantic similarity.
  * **Processing:** Develop ETL pipelines to enrich the data with NLP models (entity recognition, topic modeling, sentiment analysis).
  * **Access:** Build a **GraphQL API** using FastAPI to provide flexible data access.
  * **UI:** Create a web-based dashboard using React/Vue for researchers and journalists to explore the data, build queries, and visualize trends.