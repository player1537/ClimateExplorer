go-th() {
    "${FUNCNAME[0]:?}-$@"
}

go-th-Setup-Climate-Data() {
    nas=/mnt/seenas2/data
    data=${nas:?}${root:?}/data

    for src in "${nas:?}"/climate/gen/{UGRD,VGRD,VVEL}-144x73.dat; do 
        dst=${data:?}/${src##*/}

        ln -sf \
            "${src:?}" \
            "${dst:?}" \
            ##
    done
}
