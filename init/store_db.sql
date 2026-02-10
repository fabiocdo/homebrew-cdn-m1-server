create table homebrews
(
    pid                 INTEGER           not null
        constraint homebrews_pk
            primary key autoincrement,
    id                  TEXT              not null,
    name                TEXT              not null,
    desc                TEXT,
    image               TEXT              not null,
    package             TEXT              not null,
    version             TEXT              not null,
    picpath             TEXT,
    desc_1              TEXT,
    desc_2              TEXT,
    ReviewStars         REAL,
    Size                INTEGER           not null,
    Author              TEXT,
    apptype             TEXT              not null,
    pv                  TEXT,
    main_icon_path      TEXT,
    main_menu_pic       TEXT,
    releaseddate        TEXT              not null,
    number_of_downloads INTEGER default 0 not null,
    github              TEXT,
    video               TEXT,
    twitter             TEXT,
    md5                 TEXT,
    constraint homebrews_unique_key
        unique (version, id)
);

