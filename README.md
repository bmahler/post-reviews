## post-reviews.py

This is a wrapper around the post-review tool provided by Review Board.
This is currently used by Apache Mesos development.

### What does this do?
It provides the ability to send a review for each commit on the current branch.

### Why is that useful?
No one likes a 5000 line review request.
Using this tool forces one to create logical commits which can be reviewed independently.

### How do I use it?
Post-reviews is currently specific to mesos development, but can easily be adapted for other teams.

$ cd /path/to/messos
$ [ do some work on your branch off of trunk, make commit(s) ]
$ post-reviews
