# Mimeo

Mimeo: A tool to generate websites quickly.

I have over 70 domains. I bought them because I liked the name, or because I had the idea that someday I would do something with them. Most of them have been lying fallow in their registrars accumulating renewal fees.

One of the reasons I have never even planted a landing page on any of them is because of the "paperwork" involved in finding a place to host the landing page, setting up the DNS on the registrar to point to the landing page, creating the page, etc. etc.

## Requirements

Given a domain name `example.com` registered at a registrar, create a landing page for it hosted on a host.

### Constraints

- No manual steps.
- Use APIs to manage host and registrar
- No cost or very low cost host

For our initial implementation, we'll be using [Porkbun](https://porkbun.com) as the registrar and GitHub pages as the host.

## Operation

Mimeo is a tool to provision websites. It should look something like this:

```bash
$ mimeo idiosynthesis.org --host github --registrar porkbun --content minimal
```

This sets off two processes, one on the host (GitHub Pages)
the oher at the registrar (porkbun)

### At the registrar (porkbun)

- go to the  registrar `porkbun` and set up DNS according to the [GitHub Pages documentation](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)


### On the host (GitHub Pages)

- creates a local repo named `idiosynthesis.org` in `./mimeo-sites`
- populates it with `index.html` that displays `idiosynthesis.org` in pleasing manner (the's the `minimal` content)
- creates a remote repo on GitHub named `idiosynthesis.org`
- sets up GitHub Pages workflow for deploying to pages


### Reference sites

The reference site is:

- website: [https://mimeo.lol](https://mimeo.lol)
- github: [pborenstein/mimeo.lol](https://github.com/pborenstein/mimeo.lol/settings/pages)

## Resources

- [Porkbun AP](https://porkbun.com/api/json/v3/documentation)
