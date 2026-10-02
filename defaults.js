"use strict";
// Starting command list. You can edit all of this later in /admin.
const c = (name, category, usage, description, extra = {}) => ({ name, category, usage, description, staff: false, prefixOnly: false, ...extra });

module.exports.commands = [
  // Moderation
  c("ban", "Moderation", "ban @member [reason]", "Bans a member. They get a DM with an Appeal button that takes them to your appeal server.", { staff: true }),
  c("kick", "Moderation", "kick @member [reason]", "Kicks a member and sends them a DM.", { staff: true }),
  c("warn", "Moderation", "warn @member [reason]", "Warns a member. At 5 warnings they are kicked automatically.", { staff: true }),
  c("timeout", "Moderation", "timeout @member 10m [reason]", "Mutes a member for the time you choose (10m, 2h, 1d). No DM is sent.", { staff: true }),
  c("untimeout", "Moderation", "untimeout @member", "Removes a member's timeout.", { staff: true }),
  c("jail", "Moderation", "jail @member [reason]", "Jails a member: takes their roles and locks them into the jail channel.", { staff: true }),
  c("unjail", "Moderation", "unjail @member", "Releases a jailed member and gives their roles back.", { staff: true }),
  c("lock", "Moderation", "lock [#channel]", "Locks a channel so members can't send messages or create threads.", { staff: true }),
  c("unlock", "Moderation", "unlock [#channel]", "Unlocks a locked channel.", { staff: true }),
  c("slowmode", "Moderation", "slowmode 10s [#channel]", "Sets the slowmode of a channel. Use 0 to turn it off.", { staff: true }),
  c("role give", "Moderation", "role give @member @role", "Gives a role to a member, or to everyone if you use @everyone.", { staff: true }),
  c("role make", "Moderation", "role make #ff0000 Name", "Creates a role with the color and name you choose.", { staff: true }),
  // Utility
  c("setup", "Utility", "setup", "Opens the setup menu: staff role, logs, appeal server, tickets, welcome, security and more.", { staff: true }),
  c("afk", "Utility", "afk [reason]", "Sets you as AFK. Anyone who pings you is told you're away and their ping is blocked."),
  c("stick", "Utility", "stick <message>", "Keeps a message at the bottom of the channel. It is re-sent whenever someone talks.", { staff: true }),
  c("unstick", "Utility", "unstick", "Stops sticking the message in this channel.", { staff: true }),
  c("autoreaction", "Utility", "autoreaction #channel 🔥", "Reacts with your emoji to every message in a channel.", { staff: true }),
  c("proof", "Utility", "proof", "Inside a ticket: asks the ticket owner to post a screenshot and sends it to the proof channel.", { staff: true, prefixOnly: true }),
  c("vouch", "Utility", "vouch @member", "Vouches for a member in the vouch channel. Only works there.", { prefixOnly: true }),
  // Invites
  c("invites", "Invites", "invites [@member]", "Shows real, fake, left, rejoined and J4J invites."),
  c("invited", "Invites", "invited [@member]", "Lists the people a member invited. Only clean, real invites."),
  c("inviter", "Invites", "inviter [@member]", "Shows who invited a member."),
  c("reset invites", "Invites", "reset invites @member", "Resets a member's invites, or everyone's with @everyone.", { staff: true }),
  // Giveaways
  c("giveaway start", "Giveaways", 'giveaway 1h 2 "Prize"', "Starts a giveaway with a prize, a timer, winners and an optional photo.", { staff: true }),
  c("giveaway end", "Giveaways", "giveaway end <message id>", "Ends a giveaway right now and picks the winners.", { staff: true }),
  c("giveaway reroll", "Giveaways", "giveaway reroll <message id>", "Picks new winners for an ended giveaway.", { staff: true, prefixOnly: true }),
  // Games
  c("daily", "Games", "daily", "Claim your 500 coins every day."),
  c("balance", "Games", "balance", "Shows how many coins you have."),
  c("coinflip", "Games", "coinflip 100 heads", "Flip a coin and double your bet if you call it right."),
  c("highlow", "Games", "highlow 100", "Guess if the next number is higher or lower."),
  c("blackjack", "Games", "blackjack 100", "Play blackjack against the dealer."),
  c("roulette", "Games", "roulette 100 red", "Bet on a color, even/odd, high/low or a number."),
];

module.exports.announcements = [
  {
    id: "welcome",
    title: "The new Testiny website is live",
    body: "Commands, updates and announcements all live here now.\nLog in at /admin to post your own announcements.",
    tag: "new",
    pinned: true,
    date: Date.now(),
  },
];
