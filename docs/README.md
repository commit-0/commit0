```
python update_submissions_dataset.py
cd ../
python docs/render_submissions.py --analyze_submissions --render_webpages --split lite
```

```
cd ../commit-0.github.io
mkdocs gh-deploy --config-file ../commit0/mkdocs.yml --remote-branch master
```
