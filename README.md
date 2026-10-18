# tubevault-sidestore

Unofficial SideStore view of BallerMC's TubeVault.

BallerMC's repo doesn't work properly in SideStore. Each build is listed under
a synthetic identifier like
`com.google.ios.youtube.ytplus.cracked.6.0.beta.2.21.39.4.spyg.bonus.tweaks`
so the repo can show different tweaked versions as separate cards, but that
identifier doesn't match the real bundle ID inside the IPA
(`com.google.ios.youtube`). SideStore rejects the mismatch, and the result is
dozens of near-identical YouTube icons you can't install. Finding a specific
build meant digging through Reddit for a direct link. This fixes that.

- Web catalogue: https://ravier1.github.io/tubevault-sidestore/
- Upstream: https://repo.ballermc.com/repo.json

Open the catalogue in Safari, search, tap Install. Every build links to
BallerMC's original IPA URL. All builds share the same real bundle ID, so
installing one replaces any other. The catalogue refreshes daily at 06:00 UTC
and shows a "Last updated" timestamp at the top of the page.

## About

I built this because the TubeVault repo just wouldn't install in SideStore
and I got tired of hunting through Reddit threads for a direct link. It reads
BallerMC's public `repo.json`, groups the builds by app, and gives every
build its own install button. That's all it does.

I'm not a developer. This is a small thing I put together because the
catalogue should work and it didn't. If something breaks, open an issue and
I'll take a look.

## Support

Free to use, no strings. If it saved you some time, a coffee is appreciated
but never expected:

- https://ko-fi.com/ravier1

## Credits

All builds, all IPAs, and the original catalogue belong to
[BallerMC / TubeVault](https://github.com/ballermc) and the individual tweak
authors named in each build's description. This project is only a converter
and a viewer — it does not create, host, mirror, or modify any binary.

## Disclaimer

Not affiliated with BallerMC, Google, Spotify, YouTube, or any tweak author.
Use at your own risk. Takedown requests: open an issue.