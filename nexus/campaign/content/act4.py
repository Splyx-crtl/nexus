"""Act IV — The Keys (levels 71-95, docs/story/02-acts-and-levels.md). Written after Acts I-III and V, once B5
(crypto/analysis commands) existed to support it. No live network targets here — Mira hands the player Priya Shah's
leaked ticket export, and the act is entirely about what the files themselves hide: base64, hex dumps, checksums,
archives, metadata, and (by the end) real decryption. Chapter 1 (71-78) is written: Priya Shah is introduced the only
way she ever appears (through her own words in a ticket thread, never in person), and the chapter closes having
confirmed someone at Nexus Company noticed her asking questions about "ARCHITECT-staging." Chapters 2-3 (79-95,
including the act's climax — the confirmed reveal that NEXUS is Nexus Company technology) are not written yet.
"""
from __future__ import annotations

from ..mission import Mission, Objective

ACT4_CHAPTER1 = [
    Mission(
        id="act4_m71", number=71, act=4, size="mini", title="Encoded in Plain Sight", scenario="keys_base64",
        requires=["act3_m70"],
        briefing=["MIRA: Priya's ticket queue leaked out with the rest of the export. The target field points at a "
                  "separate file, and that one isn't plain text — decode it."],
        debrief=["MIRA: 'architect-staging-02.' A hostname, nothing more yet. But that word again."],
        objectives=[Objective(event="command", match={"name": "base64", "args__contains": "-d", "status": 0}, text="Decode the escalation target (base64 -d)",
                              hints=["base64 -d reverses the encoding.", "Try: base64 -d tickets/target.b64", "base64 -d tickets/target.b64"])],
        solution=["cat tickets/ticket_4471.txt", "base64 -d tickets/target.b64"], reward_xp=55, tags=["bash", "act4"],
    ),
    Mission(
        id="act4_m72", number=72, act=4, size="mini", title="Not a Text File", scenario="keys_xxd",
        requires=["act4_m71"],
        briefing=["NEXUS: That attachment isn't going to read like a normal file. Look at the actual bytes."],
        debrief=["NEXUS: A header nobody bothered to document. File it — it'll matter once you know what to compare "
                 "it against."],
        objectives=[Objective(event="command", match={"name": "xxd", "status": 0}, text="Hex-dump the attachment (xxd)",
                              hints=["xxd shows a file's raw bytes, not its text.", "Try: xxd tickets/signal.dat", "xxd tickets/signal.dat"])],
        solution=["xxd tickets/signal.dat"], reward_xp=45, tags=["bash", "act4"],
    ),
    Mission(
        id="act4_m73", number=73, act=4, size="standard", title="Trust, But Verify", scenario="keys_checksums",
        requires=["act4_m72"],
        briefing=["MIRA: Priya checksums every backup before trusting it. Do the same — manifest.md5 has what each "
                  "file should hash to."],
        debrief=["MIRA: backup2.cfg doesn't match. Someone edited a backup after the fact and didn't update the "
                 "record. That's either sloppy, or it's exactly what it looks like."],
        objectives=[Objective(event="command", match={"name": "md5sum", "args__contains": "-c", "status": 1}, text="Verify both backups against the manifest (md5sum -c)",
                              hints=["The manifest uses bare filenames, so check from inside that folder.",
                                    "Try: cd tickets, then md5sum -c manifest.md5", "cd tickets\nmd5sum -c manifest.md5"])],
        solution=["cd tickets", "md5sum -c manifest.md5"], reward_xp=80, tags=["bash", "act4", "md5sum"],
    ),
    Mission(
        id="act4_m74", number=74, act=4, size="story", title="The Sysadmin Who Asks Too Many Questions", scenario="keys_priya",
        requires=["act4_m73"],
        briefing=["NEXUS: There's a name attached to half these tickets. Read the thread."],
        debrief=["NEXUS: 'Forget I asked.' Someone told her to drop it, and she wrote that down anyway, for the "
                 "record nobody reads. I like her already.",
                 "MIRA: Priya Shah. Sysadmin, not an operator, not one of us. Just someone doing her job who noticed "
                 "the job didn't add up."],
        objectives=[Objective(event="file_read", match={"path__glob": "*thread_priya_227.txt"}, text="Read Priya's ticket thread",
                              hints=["It's in the tickets folder.", "Try: cat tickets/thread_priya_227.txt", "cat tickets/thread_priya_227.txt"])],
        solution=["cat tickets/thread_priya_227.txt"], reward_xp=100, tags=["bash", "act4", "story", "priya-shah"],
    ),
    Mission(
        id="act4_m75", number=75, act=4, size="mini", title="Buried in the Noise", scenario="keys_strings",
        requires=["act4_m74"],
        briefing=["MIRA: That log looks corrupted. Might not all be noise — pull out anything actually readable."],
        debrief=["MIRA: 'rotation-key-pending-review.' One real phrase in a file built to look like garbage."],
        objectives=[Objective(event="command", match={"name": "strings", "status": 0}, text="Pull the readable text out of the corrupted log",
                              hints=["strings finds printable text inside a file that otherwise looks like noise.",
                                    "Try: strings tickets/corrupt_export.log", "strings tickets/corrupt_export.log"])],
        solution=["strings tickets/corrupt_export.log"], reward_xp=50, tags=["bash", "act4"],
    ),
    Mission(
        id="act4_m76", number=76, act=4, size="standard", title="What's Actually in the Box", scenario="keys_tar",
        requires=["act4_m75"],
        briefing=["MIRA: Priya's full export came through as one archive. See what's actually in it before you dig "
                  "further."],
        debrief=["MIRA: Two more tickets. One of them is dated after the thread you just read."],
        objectives=[
            Objective(event="command", match={"name": "tar", "args__contains": "-tf", "status": 0}, text="List what's inside (tar -tf)",
                     hints=["tar -tf lists an archive's contents without extracting.", "Try: tar -tf tickets/priya_export.tar", "tar -tf tickets/priya_export.tar"]),
            Objective(event="command", match={"name": "tar", "args__contains": "-xf", "status": 0}, text="Extract it (tar -xf)",
                     hints=["tar -xf unpacks an archive into the current folder.", "Try: tar -xf tickets/priya_export.tar", "tar -xf tickets/priya_export.tar"]),
        ],
        solution=["tar -tf tickets/priya_export.tar", "tar -xf tickets/priya_export.tar"], reward_xp=90, tags=["bash", "act4", "tar"],
    ),
    Mission(
        id="act4_m77", number=77, act=4, size="mini", title="One More Check", scenario="keys_verify2",
        requires=["act4_m76"],
        briefing=["NEXUS: That last ticket is the one worth being sure about. Hash it properly this time — sha256, "
                  "not md5."],
        debrief=["NEXUS: Filed, fingerprinted, can't be quietly altered without us knowing."],
        objectives=[Objective(event="command", match={"name": "sha256sum", "status": 0}, text="Hash the ticket (sha256sum)",
                              hints=["sha256sum is the stronger, modern version of md5sum.", "Try: sha256sum tickets/ticket_4501.txt", "sha256sum tickets/ticket_4501.txt"])],
        solution=["sha256sum tickets/ticket_4501.txt"], reward_xp=40, tags=["bash", "act4", "sha256sum"],
    ),
    Mission(
        id="act4_m78", number=78, act=4, size="milestone", title="Everything Priya Left Behind", scenario="keys_dossier",
        requires=["act4_m77"],
        briefing=["MIRA: Everything her export actually told us, one file, archived."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: A sysadmin got reassigned for asking about a backup rotation. That's a strange amount of "
                 "effort to spend on something boring. We're not done with 'ARCHITECT-staging.'"],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*priya_summary.txt"}, text="Assemble the findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r ARCHITECT keysnotes | tee priya_summary.txt",
                           "grep -r ARCHITECT keysnotes | tee priya_summary.txt\ncat priya_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp priya_summary.txt /archive/priya_summary.txt",
                           "sudo cp priya_summary.txt /archive/priya_summary.txt"]),
        ],
        solution=["grep -r ARCHITECT keysnotes | tee priya_summary.txt", "cat priya_summary.txt", "sudo cp priya_summary.txt /archive/priya_summary.txt"],
        reward_xp=210, tags=["bash", "act4", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT4_CHAPTER2 = [
    Mission(
        id="act4_m79", number=79, act=4, size="mini", title="A Policy Nobody Questions", scenario="keys_unzip",
        requires=["act4_m78"],
        briefing=["MIRA: Priya forwarded something else — a policy doc, zipped. See what it actually says."],
        debrief=["MIRA: 'Escalation routes through Compliance, not IT.' That's not standard. That's a wall built on "
                 "purpose."],
        objectives=[
            Objective(event="command", match={"name": "unzip", "status": 0}, text="Unzip the policy doc (unzip)",
                     hints=["unzip reverses zip.", "Try: unzip tickets/policy.zip", "unzip tickets/policy.zip"]),
            Objective(event="file_read", match={"path__glob": "*architect_staging_policy.txt"}, text="Read it",
                     hints=["It extracted into the current folder.", "Try: cat architect_staging_policy.txt", "cat architect_staging_policy.txt"]),
        ],
        solution=["unzip tickets/policy.zip", "cat architect_staging_policy.txt"], reward_xp=60, tags=["bash", "act4", "zip"],
    ),
    Mission(
        id="act4_m80", number=80, act=4, size="standard", title="Locked Before She'd Even Send It", scenario="keys_gpg",
        requires=["act4_m79"],
        briefing=["MIRA: Priya's actual contact gave us the phrase for this one: 'threshold-protocol'. She encrypted "
                  "this note before she'd even forward it to someone she trusted."],
        debrief=["MIRA: Someone on an 'ARCHITECT distribution list.' She has the name. She's not writing it down "
                 "anywhere we can read yet."],
        objectives=[Objective(event="file_read", match={"path__glob": "*escalation_note.txt.gpg"}, text="Decrypt Priya's note (gpg --decrypt)",
                              hints=["gpg --decrypt needs the passphrase and, usually, an output file.",
                                    "Try: gpg --decrypt --batch --passphrase threshold-protocol tickets/escalation_note.txt.gpg",
                                    "gpg --decrypt --batch --passphrase threshold-protocol tickets/escalation_note.txt.gpg"])],
        solution=["gpg --decrypt --batch --passphrase threshold-protocol tickets/escalation_note.txt.gpg"],
        reward_xp=100, tags=["bash", "act4", "gpg"],
    ),
    Mission(
        id="act4_m81", number=81, act=4, size="story", title="Not a Ticket, a Phone Call", scenario="keys_watched",
        requires=["act4_m80"],
        briefing=["NEXUS: She's getting nervous. Read the latest thread."],
        debrief=["NEXUS: 'Probably paranoid. Probably fine.' People only say that when it's neither.",
                 "MIRA: She doesn't know we exist. She's not being careful because of us. That should worry you more, "
                 "not less."],
        objectives=[Objective(event="file_read", match={"path__glob": "*thread_priya_244.txt"}, text="Read Priya's latest thread",
                              hints=["It's in the tickets folder.", "Try: cat tickets/thread_priya_244.txt", "cat tickets/thread_priya_244.txt"])],
        solution=["cat tickets/thread_priya_244.txt"], reward_xp=85, tags=["bash", "act4", "story", "priya-shah"],
    ),
    Mission(
        id="act4_m82", number=82, act=4, size="mini", title="The Published Number Lies", scenario="keys_tamper_check",
        requires=["act4_m81"],
        briefing=["MIRA: The internal wiki publishes a checksum for that config, supposedly so people can verify it "
                  "hasn't changed. Check it against the real thing."],
        debrief=["MIRA: Doesn't match. The published hash is for a version that doesn't exist on disk anymore. "
                 "Someone updated the file and never touched the public record."],
        objectives=[Objective(event="command", match={"name": "openssl", "args__contains": "dgst", "status": 0}, text="Hash the real config (openssl dgst)",
                              hints=["openssl dgst -sha256 hashes a file the way sha256sum does, just spelled differently.",
                                    "Try: openssl dgst -sha256 tickets/staging_config.txt", "openssl dgst -sha256 tickets/staging_config.txt"])],
        solution=["openssl dgst -sha256 tickets/staging_config.txt", "cat tickets/wiki_published_hash.txt"],
        reward_xp=65, tags=["bash", "act4", "openssl"],
    ),
    Mission(
        id="act4_m83", number=83, act=4, size="standard", title="A Department, Not Just a Project", scenario="keys_exif",
        requires=["act4_m82"],
        briefing=["MIRA: There's a quarterly review document in the export. Check what it's actually carrying in its "
                  "metadata, not just what it says on the page."],
        debrief=["NEXUS: 'ARCHITECT Program Office.' Not a project codename anymore. An actual department, with "
                 "actual staff, doing actual work. Someone built an org chart around this."],
        objectives=[Objective(event="file_identified", match={"path__glob": "*quarterly_review.doc"}, text="Check the document's metadata (exiftool)",
                              hints=["exiftool reads metadata a document carries that isn't part of the visible text.",
                                    "Try: exiftool tickets/quarterly_review.doc", "exiftool tickets/quarterly_review.doc"])],
        solution=["exiftool tickets/quarterly_review.doc"], reward_xp=95, tags=["bash", "act4", "exiftool"],
    ),
    Mission(
        id="act4_m84", number=84, act=4, size="mini", title="A Strange Size for a Photo", scenario="keys_binwalk",
        requires=["act4_m83"],
        briefing=["NEXUS: That photo is a strange size for what it's supposed to be. Scan it."],
        debrief=["NEXUS: Something's embedded in there. Nothing here to pull it out with yet — but now we know to "
                 "come back for it."],
        objectives=[Objective(event="command", match={"name": "binwalk", "status": 0}, text="Scan the photo for hidden data (binwalk)",
                              hints=["binwalk looks for the telltale first bytes of other file formats hidden inside a file.",
                                    "Try: binwalk tickets/quarterly_photo.jpg", "binwalk tickets/quarterly_photo.jpg"])],
        solution=["binwalk tickets/quarterly_photo.jpg"], reward_xp=50, tags=["bash", "act4", "binwalk"],
    ),
    Mission(
        id="act4_m85", number=85, act=4, size="standard", title="Locked Twice", scenario="keys_layered",
        requires=["act4_m84"],
        briefing=["MIRA: This one's locked twice. Peel it back one layer at a time — the zip first, then whatever "
                  "it points you at."],
        debrief=["MIRA: 'Compliance review requested for ARCHITECT distribution list, flagged urgent.' Two locks for "
                 "one paragraph. That's not bureaucracy. That's someone being careful."],
        objectives=[
            Objective(event="command", match={"name": "unzip", "status": 0}, text="Unzip the outer layer (unzip)",
                     hints=["Same as before — unzip the archive first.", "Try: unzip tickets/compliance_review.zip", "unzip tickets/compliance_review.zip"]),
            Objective(event="file_read", match={"path__glob": "*compliance_note.txt.gpg"}, text="Decrypt what's inside (gpg --decrypt)",
                     hints=["The README the zip extracts points at where the real encrypted note actually is. The passphrase "
                           "from Level 80 still works — Priya reuses it.",
                           "Try: gpg --decrypt --batch --passphrase threshold-protocol tickets/compliance_note.txt.gpg",
                           "gpg --decrypt --batch --passphrase threshold-protocol tickets/compliance_note.txt.gpg"]),
        ],
        solution=["unzip tickets/compliance_review.zip", "cat README.txt", "gpg --decrypt --batch --passphrase threshold-protocol tickets/compliance_note.txt.gpg"],
        reward_xp=110, tags=["bash", "act4", "zip", "gpg"],
    ),
    Mission(
        id="act4_m86", number=86, act=4, size="story", title="Signing Off", scenario="keys_farewell",
        requires=["act4_m85"],
        briefing=["NEXUS: One more message from Priya. Probably her last."],
        debrief=["NEXUS: 'Staging-vault.' A name, finally, instead of a codename for a codename.",
                 "MIRA: That's where we go next. Carefully. She warned us for a reason, even if she didn't mean to."],
        objectives=[Objective(event="file_read", match={"path__glob": "*thread_priya_final.txt"}, text="Read Priya's final message",
                              hints=["It's in the tickets folder.", "Try: cat tickets/thread_priya_final.txt", "cat tickets/thread_priya_final.txt"])],
        solution=["cat tickets/thread_priya_final.txt"], reward_xp=120, tags=["bash", "act4", "story", "priya-shah"],
    ),
    Mission(
        id="act4_m87", number=87, act=4, size="milestone", title="Before Staging-Vault", scenario="keys_dossier2",
        requires=["act4_m86"],
        briefing=["MIRA: Everything from this chapter, one file, before we go after staging-vault itself."],
        debrief=["MIRA: Filed and locked. Chapter closed.",
                 "NEXUS: Walled-off escalation routes, a department with a name, a vault nobody on the inside was "
                 "trusted with. Whatever's actually in it, it's not a routine backup. Let's go find out."],
        objectives=[
            Objective(event="file_read", match={"path__glob": "*keys_summary.txt"}, text="Assemble the chapter's findings (grep -r ... | tee)",
                     hints=["Same habit as every chapter close so far.", "Try: grep -r staging-vault keysnotes | tee keys_summary.txt",
                           "grep -r staging-vault keysnotes | tee keys_summary.txt\ncat keys_summary.txt"]),
            Objective(event="sudo_used", match={"command": "cp"}, text="Archive it (sudo cp)",
                     hints=["It lives at /archive, at the filesystem root.", "Try: sudo cp keys_summary.txt /archive/keys_summary.txt",
                           "sudo cp keys_summary.txt /archive/keys_summary.txt"]),
        ],
        solution=["grep -r staging-vault keysnotes | tee keys_summary.txt", "cat keys_summary.txt", "sudo cp keys_summary.txt /archive/keys_summary.txt"],
        reward_xp=220, tags=["bash", "act4", "milestone", "grep", "tee", "sudo"],
    ),
]

ACT4 = [*ACT4_CHAPTER1, *ACT4_CHAPTER2]
