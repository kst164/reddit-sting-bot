import psycopg2
import psycopg2.extras
import praw
import os

conn = psycopg2.connect(database="redditbot", user="kartheek")
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

reddit = praw.Reddit(
    user_agent=os.environ["USER_AGENT"],
    refresh_token=os.environ["REFRESH_TOKEN"],
    client_id=os.environ["CLIENT_ID"],
    client_secret=os.environ["CLIENT_SECRET"],
)


def getAuthorRow(post):
    # Returns DB entry of author of comment/submission if they have been stung before, else None

    cur.execute("SELECT * FROM stingTree WHERE username = %s", [post.author.name])
    if (cur.rowcount > 0):
        return cur.fetchone()
    else:
        return None

def getParent(comment):
    # If parent is a submission, comment.parent_id starts with "t3_"
    # Else, it starts with "t1_"

    if (comment.parent_id[:3] == "t1_"):
        # Not a top level comment
        return reddit.comment(comment.parent_id[3:])
    else:
        # Top level comment
        return reddit.submission(comment.parent_id[3:])

def sting(stung_by, sting, depth, username):
    cur.execute("INSERT INTO stingTree (stung_by, sting, depth, username) VALUES (%s, %s, %s, %s)", (stung_by, sting, depth, username))
    conn.commit()


replyTemplates = {
    "notStung" : "Sorry, u/{stinger}, you have to be stung first before you can sting other people.",
    "alreadyStung" : "Sorry, u/{stingee} was already stung [here]({stingLink}).",
    "success" : "u/{stingee}, you have been stung.",
    "base" : "This was an automated reply based on [this post]({infoLink})"
}

for comment in reddit.subreddit("kst164").stream.comments():
    if (comment.body == "!STING"):
        stingerRow = getAuthorRow(comment)
        parent = getParent(comment)
        stingeeRow = getAuthorRow(parent)

        reply = ""

        if stingerRow == None:
            # Wasn't stung in the first place
            reply = replyTemplates["notStung"].format(stinger = comment.author.name)

        elif stingeeRow is not None:
            if (comment.id == stingeeRow["sting"]):
                # We're just reading the same comment again
                continue

            # Was already stung
            lastSting = reddit.comment(stingeeRow["sting"])
            stingLink = "https://reddit.com" + lastSting.permalink + "?context=1"
            reply = replyTemplates["alreadyStung"].format(stingee = parent.author.name, stingLink = stingLink)

            # Save sting for later
            cur.execute("INSERT INTO erdosStings (comment) VALUES (%s)", (comment.id,))
            conn.commit()

        else:
            # Actual successful sting

            reply = replyTemplates["success"].format(stingee = parent.author.name)
            sting(stingerRow["id"], comment.id, stingerRow["depth"] + 1, parent.author.name)

        reply = reply + "\n\n\n" + replyTemplates["base"].format(infoLink="")
        print(f"comment: {comment}\nreply: {reply}\n")

        comment.reply(reply)
