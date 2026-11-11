# Patches

Drop your patches here. They are applied in filename order, so prefix with numbers:

    0001-tu-force-something.patch
    0002-disable-feature-x.patch

## Making a patch

Best (keeps authorship and commit message, applied with `git am`):

    cd work/mesa           # after running build.sh once
    # edit files, then:
    git commit -am "tu: describe change"
    git format-patch -1 -o ../../patches --start-number 1

Plain diffs (`*.diff` / `git diff > x.patch`) also work and are applied with `git apply --3way`.

## When upstream moves

If a patch no longer applies, the CI build fails and tells you which one.
Rebase it against current Mesa, regenerate, commit.
