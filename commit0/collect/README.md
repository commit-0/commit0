# create-data

Code for create the spec2repo dataset.

To convert a specification on web to a PDF:
```
python scrape_pdf.py [base_url_of_spec] [out_dir]
```
For example,
```
python scrape_pdf.py https://minitorch.github.io/ pdfs
```

To serialize a repository to text:
```
python serialize_repo.py [repo_dir] > [output_file]
```
For example,
```
python serialize_repo.py minitorch/ > minitorch_repo.txt
```

To read texts from a PDF:
```
python pdf2text.py [path_to_pdf] > [output_file]
```
For example,
```
python pdf2text.py pdfs/complete.pdf > minitorch.txt
```
