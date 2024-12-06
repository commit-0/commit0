
Update HF dataset then:
```
python docs/update_submissions_dataset.py
```

Run submissions analysis on SPLIT
```
python docs/render_submissions.py 
                       --do_setup --get_blank_details --get_reference_details # only once, at beginning of setting up environment
                       --analyze_submissions 
                       --split SPLIT
```

Render webpages on submissions.
```
python docs/render_submissions.py --render_webpages --overwrite_previous_eval
```

Deploy to website.
```
cd ../commit-0.github.io
mkdocs gh-deploy --config-file ../commit0/mkdocs.yml --remote-branch main
```