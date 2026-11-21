# Patches

Everything here is applied in filename order to upstream Mesa (`git am --3way`, then `git apply --3way` as a fallback).
Prefix names with numbers: `0001-tu-...patch`.

## Making a patch

Best (keeps authorship and commit message):

    cd work/mesa           # after running build.sh once
    # edit files, then:
    git commit -am "tu: describe change"
    git format-patch -1 -o ../../patches --start-number 5

Plain diffs (`*.diff` / `git diff > x.patch`) also work and are applied with `git apply --3way`.

## Without a local Mesa checkout

Run the "Inspect Mesa" workflow (Actions tab). It force-pushes the current Turnip sources to the `inspect-src`
branch of this repo, so you can fetch that branch, edit, commit and `git format-patch` there.

## When upstream moves

If a patch no longer applies, the CI build fails and prints the rejected hunks together with the current upstream
code around them. Rebase it, regenerate it and keep the number prefix.

## Current series

`0001` to `0008` are described in the top-level README.
