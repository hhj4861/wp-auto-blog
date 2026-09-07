<?php
/**
 * Plugin Name: WPAB REST Settings Bridge
 * Description: 파이프라인이 원격(REST)으로 설정해야 하는 옵션을 /wp/v2/settings 에 노출한다.
 *              (1) 댓글 승인 정책  (2) Yoast 아카이브 색인 여부 — Yoast는 이 설정을 REST로
 *              노출하지 않아 UI 수동 토글 외에는 바꿀 방법이 없다.
 * Author: wp-auto-blog
 * Version: 1.1.0
 *
 * Install: wp-content/mu-plugins/ 에 업로드 (활성화 절차 불필요).
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * wpab_archive_index 의 키 → Yoast wpseo_titles 키.
 * 의미가 반대다: 이 브릿지는 "색인할까?"(true=색인), Yoast는 "noindex 할까?"(true=제외).
 */
function wpab_archive_index_map() {
	return array(
		'category' => 'noindex-tax-category',
		'post_tag' => 'noindex-tax-post_tag',
		'author'   => 'noindex-author-wpseo',
		'date'     => 'noindex-archive-wpseo',
	);
}

add_action( 'init', function () {
	$options = array(
		'comment_moderation',           // '1' = 모든 댓글 수동 승인 대기, '0' = 자동 승인
		'comment_previously_approved',  // '1' = 첫 댓글만 대기(재승인자 자동), '0' = 이력 무관
	);

	foreach ( $options as $option ) {
		register_setting( 'discussion', $option, array(
			'show_in_rest' => true,
			'type'         => 'string',
			'description'  => 'WPAB remote comment approval policy',
		) );
	}

	// Yoast 아카이브 색인 브릿지. true = 검색결과에 노출(색인), false = noindex.
	register_setting( 'wpab', 'wpab_archive_index', array(
		'type'         => 'object',
		'description'  => 'WPAB bridge for Yoast archive indexing (true = indexable)',
		'default'      => array(),
		'show_in_rest' => array(
			'schema' => array(
				'type'                 => 'object',
				'properties'           => array(
					'category' => array( 'type' => 'boolean' ),
					'post_tag' => array( 'type' => 'boolean' ),
					'author'   => array( 'type' => 'boolean' ),
					'date'     => array( 'type' => 'boolean' ),
				),
				'additionalProperties' => false,
			),
		),
	) );
} );

/**
 * 읽기: 저장값이 아니라 Yoast의 실제 상태를 돌려준다(둘이 어긋날 여지를 없앤다).
 * 옵션 행이 아직 없으면 WordPress는 option_* 대신 default_option_* 을 태우므로 양쪽에 건다.
 */
$wpab_archive_index_read = function ( $value ) {
	if ( ! class_exists( 'WPSEO_Options' ) ) {
		return $value;
	}
	$state = array();
	foreach ( wpab_archive_index_map() as $key => $yoast_key ) {
		$state[ $key ] = ! (bool) WPSEO_Options::get( $yoast_key, false );
	}
	return $state;
};
add_filter( 'option_wpab_archive_index', $wpab_archive_index_read );
add_filter( 'default_option_wpab_archive_index', $wpab_archive_index_read );

/** 쓰기: 보내온 키만 Yoast 옵션에 반영한다(나머지 Yoast 설정은 건드리지 않는다). */
add_filter( 'pre_update_option_wpab_archive_index', function ( $new_value, $old_value ) {
	if ( ! class_exists( 'WPSEO_Options' ) || ! is_array( $new_value ) ) {
		return $new_value;
	}
	foreach ( wpab_archive_index_map() as $key => $yoast_key ) {
		if ( array_key_exists( $key, $new_value ) ) {
			WPSEO_Options::set( $yoast_key, ! (bool) $new_value[ $key ] );
		}
	}
	return $new_value;
}, 10, 2 );
