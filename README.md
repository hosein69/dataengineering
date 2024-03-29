**Project Title: Introduction to Data Engineering**

**Overview:**

Welcome to my journey into the realm of data engineering! This repository marks the beginning of my exploration into the fascinating world of organizing, processing, and analyzing data at scale. As I embark on this learning adventure, I invite you to join me in discovering the fundamental concepts and tools that form the backbone of data engineering.

**Project Structure:**

1. <ins> Postgres ETL </ins> :heavy_check_mark:
* This project looks at data modelling for a fictitious music startup Sparkify, applying STAR schema to ingest data to simplify queries that answers business questions the product owner may have



2. <ins> Web Scrapying using Scrapy, MongoDB ETL </ins> :heavy_check_mark:
* In storing semi-structured data, one form to store it in, is in the form of documents. MongoDB makes this possible, with a specific collection containing related documents. Each document contains fields of data which can be queried. 
* In this project, data is scraped from a books listing website using Scrapy. The fields of each book, such as price of a book, ratings, whether it is available is stored in a document in the books collection in MongoDB.

3. <ins> Data Warehousing with AWS Redshift </ins> :heavy_check_mark:
* This project creates a data warehouse, in AWS Redshift. A data warehouse provides a reliable and consistent foundation for users to query and answer some business questions based on requirements.

4. <ins> Data Lake with Spark & AWS S3 </ins> :heavy_check_mark:
* This project creates a data lake, in AWS S3 using Spark. 
* Why create a data lake? A data lake provides a reliable store for large amounts of data, from unstructured to semi-structured and even structured data. In this project, we ingest json files, denormalize them into fact and dimension tables and upload them into a AWS S3 data lake, in the form of parquet files.

5. <ins> Data Pipelining with Airflow </ins> :heavy_check_mark:
* This project schedules data pipelines, to perform ETL from json files in S3 to Redshift using Airflow. 
* Why use Airflow? Airflow allows workflows to be defined as code, they become more maintainable, versionable, testable, and collaborative

**Getting Started:**

To get started with the project, follow these steps:

1. **Clone the Repository:**
   ```
   git clone https://github.com/hosein69/dataengineering.git
   ```

2. **Navigate to the Project Directory:**
   ```
   cd dataengineering
   ```

3. **Explore the Documentation:**
   Refer to the documentation folder to access guides, tutorials, and references covering various data engineering topics.

4. **Run Examples:**
   Check out the examples folder to see practical implementations of data engineering tasks. Feel free to modify and experiment with the code.

5. **Experiment with Datasets:**
   Utilize the datasets provided in the datasets folder to practice data manipulation, processing, and analysis.

6. **Contribute:**
   If you have ideas for improvements or additional content, we welcome contributions! Please refer to the contributing guidelines for more information.

**Contributing:**

We encourage contributions from the community to enhance this project further. If you'd like to contribute, please follow these guidelines:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and ensure the codebase and documentation are up to date.
4. Test your changes thoroughly.
5. Submit a pull request, clearly describing the changes you've made.

Please note that all contributions will be reviewed before merging.

**Feedback:**

We value your feedback! If you have any questions, suggestions, or encounter issues while using this project, please don't hesitate to open an issue or reach out to us.

**License:**

This project is licensed under the MIT License. See the LICENSE file for more details.

**Acknowledgments:**

We would like to thank the open-source community for their invaluable contributions and resources that have helped make this project possible.

Thank you for exploring our data engineering introductory project! Happy coding! 🚀
