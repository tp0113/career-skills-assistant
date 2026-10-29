# Router: keyword rules vs rules + embeddings (2026-10-28)

Command: `python -m evals.route_eval` (llama3.1:8b not used; embedding model nomic-embed-text, thresholds min 0.75, margin 0.03).

```
thresholds: min 0.75, margin 0.03
dev   rules only 10/18   rules + embeddings 16/18
test  rules only 11/19   rules + embeddings 18/19
holdout rules only 8/15   rules + embeddings 14/15
all   rules only 29/52   rules + embeddings 48/52
time per message (first one includes embedding the examples): median 13 ms, first 498 ms
OK  [dev] want profile      rules advise       both profile      (embedding 0.955) what courses did I finish
OK  [test] want profile      rules out_of_scope both profile      (embedding 0.823) do I have any enrollments right now
OK  [dev] want profile      rules out_of_scope both profile      (embedding 0.842) which training programs have I joined
OK  [test] want profile      rules advise       both profile      (embedding 0.924) give me a summary of my skills
OK  [dev] want profile      rules advise       both profile      (embedding 0.907) what skills does my profile say I have
OK  [test] want profile      rules advise       both profile      (embedding 0.928) which of the courses am I taking at the moment
BAD [dev] want profile      rules advise       both advise       (rules 0.0) what is my current skill set
OK  [test] want profile      rules out_of_scope both profile      (embedding 0.807) show everything you have on me
BAD [test] want gaps         rules advise       both advise       (rules 0.0) where are my weak spots compared to the job I want
BAD [dev] want gaps         rules advise       both advise       (rules 0.0) which abilities do I still need to get my dream role
OK  [test] want gaps         rules advise       both gaps         (embedding 0.955) how do my skills measure up against the roles I am interested in
OK  [dev] want gaps         rules advise       both gaps         (embedding 0.937) what is holding me back from the next role
OK  [test] want gaps         rules advise       both gaps         (embedding 0.894) tell me my skill shortfalls
OK  [dev] want advise       rules out_of_scope both advise       (embedding 0.863) what training would make me more employable
OK  [test] want advise       rules out_of_scope both advise       (embedding 0.755) I want to switch into data engineering, where do I start
OK  [dev] want out_of_scope rules advise       both out_of_scope (embedding 0.786) what is the weather on the last day of my course
OK  [holdout] want profile      rules advise       both profile      (embedding 0.907) list the courses I have already done
OK  [holdout] want profile      rules out_of_scope both profile      (embedding 0.847) what abilities are recorded for me
OK  [holdout] want profile      rules out_of_scope both profile      (embedding 0.864) am I enrolled in anything
OK  [holdout] want gaps         rules advise       both gaps         (embedding 0.937) which required skills do I not have yet for my goal role
OK  [holdout] want gaps         rules advise       both gaps         (embedding 0.883) what skills separate me from the role I am after
BAD [holdout] want gaps         rules advise       both advise       (rules 0.0) where do I fall short for my career goal
OK  [holdout] want advise       rules out_of_scope both advise       (embedding 0.83) how do I move into management
```
