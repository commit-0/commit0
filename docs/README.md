```
python update_submissions_dataset.py
cd ../
python docs/render_submissions.py --analyze_submissions --render_webpages --split lite
```

```
cd ..
mkdocs gh-deploy --config-file mkdocs.yml --site-dir ../commit-0.github.io/ --remote-branch master
```