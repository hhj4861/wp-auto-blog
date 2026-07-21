<?php
/**
 * Plugin Name: WPAB Yoast REST Meta Bridge
 * Description: Registers Yoast SEO post meta for the REST API so the wp-auto-blog
 *              pipeline's `meta` payload (metadesc, focus keyword, SEO title, robots)
 *              actually persists. Without this, WordPress silently drops these keys.
 * Author: wp-auto-blog
 * Version: 1.0.0
 *
 * Install: upload this single file to wp-content/mu-plugins/ (create the
 * directory if it does not exist). Must-use plugins need no activation.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action( 'init', function () {
	$yoast_meta_keys = array(
		'_yoast_wpseo_metadesc',
		'_yoast_wpseo_focuskw',
		'_yoast_wpseo_title',
		'_yoast_wpseo_meta-robots-noindex',
		'_yoast_wpseo_meta-robots-nofollow',
	);

	foreach ( $yoast_meta_keys as $key ) {
		// 최신 Yoast가 이미 REST에 등록한 키(metadesc/focuskw/title 등)는 건너뛴다.
		if ( registered_meta_key_exists( 'post', $key, 'post' ) ) {
			continue;
		}
		register_post_meta( 'post', $key, array(
			'show_in_rest'  => true,
			'single'        => true,
			'type'          => 'string',
			'auth_callback' => function () {
				return current_user_can( 'edit_posts' );
			},
		) );
	}
} );
