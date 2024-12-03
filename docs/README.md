```
python update_submissions_dataset.py
cd ../
python docs/render_submissions.py --analyze_submissions --split SPLIT
python docs/render_submissions.py --render_webpages --overwrite_previous_eval
```

```
cd ../commit-0.github.io
mkdocs gh-deploy --config-file ../commit0/mkdocs.yml --remote-branch main
```
