CREATE DATABASE "rag-docs";
\c rag-docs

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE SEQUENCE IF NOT EXISTS public.data_llamaindex_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

CREATE TABLE IF NOT EXISTS public.data_llamaindex (
    id bigint NOT NULL DEFAULT nextval('public.data_llamaindex_id_seq'::regclass),
    text character varying NOT NULL,
    metadata_ json,
    node_id character varying,
    embedding public.vector(384)
);

CREATE UNIQUE INDEX IF NOT EXISTS data_llamaindex_pkey ON public.data_llamaindex USING btree (id);